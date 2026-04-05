import {
  Navbar,
  NavbarGroup,
  NavbarHeading,
  NavbarDivider,
  Button,
  Menu,
  MenuItem,
  Popover,
  Position,
  Alignment,
} from '@blueprintjs/core';
import useTranslation from 'next-translate/useTranslation';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { useSession, signIn, signOut } from 'next-auth/react';
import Image from 'next/image';
import SearchBar from './SearchBar';
import NavbarSponsors from './SponsorIcons';
import deputylogo from '../assets/logos/DEPUTY_BLUEBLUEv4.svg';

const UserMenu = () => {
  const { t } = useTranslation('common');
  const router = useRouter();

  return (
    <Menu>
      <MenuItem
        text={t('tokens')}
        onClick={() => {
          router.push('/tokens');
        }}
      />
    </Menu>
  );
};

const MainNavbar = () => {
  const { t } = useTranslation('common');
  const { data: session, update } = useSession();
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      update();
    }, 1000 * 50);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const visibilityHandler = () => {
      if (document.visibilityState === 'visible') {
        update();
      }
    };
    window.addEventListener('visibilitychange', visibilityHandler, false);
    return () =>
      window.removeEventListener('visibilitychange', visibilityHandler, false);
  }, []);

  const handleBrowsePackagesClick = () => {
    setMobileMenuOpen(false); // Close the drawer
  };

  return (
    <>
      <Navbar className="h-auto bg-cr14-dark-blue">
        <div className="flex justify-between items-center px-4 md:px-6 py-2">
          {/* Left side: Logo and sponsors */}
          <NavbarGroup
            align={Alignment.LEFT}
            className="flex items-center space-x-4"
          >
            <NavbarHeading>
              <Link href="/" className="hover:no-underline focus:outline-none">
                <span className="py-2">
                  <Image
                    className="object-contain h-8 w-8 md:h-10 md:w-10"
                    src={deputylogo}
                    alt="Deputy Logo"
                  />
                </span>
              </Link>
            </NavbarHeading>
            <NavbarSponsors />{' '}
            {/* Sponsors displayed in navbar on all screens */}
          </NavbarGroup>

          {/* Center: Links for larger screens */}
          <div className="hidden md:flex items-center space-x-4">
            <SearchBar />
            <Link
              href="/packages"
              className="bp5-button bp5-small bp5-minimal rounded-md"
            >
              <span className="text-white">{t('browseAllPackages')}</span>
            </Link>
          </div>

          {/* Right side: User actions */}
          <NavbarGroup align="right" className="hidden md:flex items-center">
            <NavbarDivider />
            {session ? (
              <>
                {session.user?.name && (
                  <Popover
                    usePortal={false}
                    content={<UserMenu />}
                    position={Position.BOTTOM}
                    autoFocus={false}
                  >
                    <Button
                      className="font-bold outline-none"
                      textClassName="text-white whitespace-nowrap rounded-md"
                      small
                      minimal
                      icon="caret-down"
                    >
                      <span className="text-white whitespace-nowrap rounded-md">
                        {session.user.name}
                      </span>
                    </Button>
                  </Popover>
                )}
                <Button
                  className="ml-2"
                  icon="log-out"
                  small
                  minimal
                  onClick={(e) => {
                    e.preventDefault();
                    signOut();
                  }}
                >
                  <span className="text-white whitespace-nowrap rounded-md">
                    {t('logOut')}
                  </span>
                </Button>
              </>
            ) : (
              <Button
                className="font-bold"
                small
                minimal
                icon="log-in"
                onClick={(e) => {
                  e.preventDefault();
                  signIn();
                }}
              >
                <span className="text-white whitespace-nowrap rounded-md">
                  {t('logIn')}
                </span>
              </Button>
            )}
          </NavbarGroup>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden">
            <Button
              icon="menu"
              minimal
              onClick={() => setMobileMenuOpen(!isMobileMenuOpen)}
            />
          </div>
        </div>
      </Navbar>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className="md:hidden bg-cr14-dark-blue px-4 py-4 flex flex-col items-center space-y-4">
          <SearchBar /> {/* Search bar inside the mobile drawer */}
          <Link
            href="/packages"
            onClick={handleBrowsePackagesClick}
            className="block text-white text-center"
          >
            {t('browseAllPackages')}
          </Link>
          <div className="border-t border-white w-full my-2" />
          {session ? (
            <>
              <Popover
                usePortal={false}
                content={<UserMenu />}
                position={Position.BOTTOM}
                autoFocus={false}
              >
                <Button className="w-full text-center text-white" minimal>
                  <span className="text-white whitespace-nowrap rounded-md">
                    {session.user?.name}
                  </span>
                </Button>
              </Popover>
              <Button
                icon="log-out"
                minimal
                className="w-full text-center text-white"
                onClick={(e) => {
                  e.preventDefault();
                  signOut();
                }}
              >
                <span className="text-white whitespace-nowrap rounded-md">
                  {t('logOut')}
                </span>
              </Button>
            </>
          ) : (
            <Button
              icon="log-in"
              minimal
              className="w-full text-center text-white"
              onClick={(e) => {
                e.preventDefault();
                signIn();
              }}
            >
              <span className="text-white whitespace-nowrap rounded-md">
                {t('logIn')}
              </span>
            </Button>
          )}
        </div>
      )}
    </>
  );
};

export default MainNavbar;
