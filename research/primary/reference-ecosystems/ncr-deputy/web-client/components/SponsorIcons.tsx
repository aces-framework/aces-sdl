import React from 'react';
import Image from 'next/image';
import easLogo from 'assets/logos/EAS=White.png';
import norwayGrantsLogo from 'assets/logos/Norway_grants_White.png';

const NavbarSponsors = () => (
  <>
    <a
      href="https://eeagrants.org/"
      target="_blank"
      rel="noopener noreferrer"
      className="h-12 w-12 m-4 relative outline-none"
    >
      <Image
        src={norwayGrantsLogo}
        alt="norwayGrants-logo"
        fill
        className="object-contain absolute py-1"
        sizes="(max-width: 60px) 10vw, 60px"
      />
    </a>
    <a
      href="https://eas.ee"
      target="_blank"
      rel="noopener noreferrer"
      className="h-20 w-20 mr-4 relative outline-none"
    >
      <Image
        src={easLogo}
        alt="eas-logo"
        fill
        className="object-contain absolute"
        sizes="(max-width: 60px) 10vw, 60px"
      />
    </a>
  </>
);

export default NavbarSponsors;
