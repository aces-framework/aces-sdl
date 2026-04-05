import React from 'react';
import {Link} from 'react-router-dom';
import {useTranslation} from 'react-i18next';

const ClientNavbarLinks = () => {
  const {t} = useTranslation();
  return (
    <Link
      role='button'
      className='bp5-button bp5-minimal bp5-icon-document'
      to='/'
    >
      {t('menu.exerciseOrders')}
    </Link>
  );
};

export default ClientNavbarLinks;
