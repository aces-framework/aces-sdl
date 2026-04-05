import React from 'react';
import easLogo from 'src/assets/logos/enterprise-estonia-eas-vector-logo.svg';
import norwayGrantsLogo from 'src/assets/logos/Norway_grants-logo.png';

const NavbarSponsors = () => (
  <>
    <a
      href='https://eeagrants.org/'
      target='_blank'
      rel='noopener noreferrer'
      className='h-full'
    >
      <img src={norwayGrantsLogo} alt='norwayGrants-logo' className='h-full px-4'/>
    </a>
    <a href='https://eas.ee' target='_blank' rel='noopener noreferrer' className='h-full'>
      <img src={easLogo} alt='eas-logo' className='h-16 pr-4'/>
    </a>
  </>
);

export default NavbarSponsors;
