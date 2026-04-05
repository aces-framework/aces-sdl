import React from 'react';
import {Link} from 'react-router-dom';
import {useTranslation} from 'react-i18next';

const ManagerNavbarLinks = () => {
  const {t} = useTranslation();
  return (
    <>
      <Link
        role='button'
        className='bp5-button bp5-minimal bp5-icon-document'
        to='/exercises'
      >
        {t('menu.exercises')}
      </Link>
      <Link
        role='button'
        className='bp5-button bp5-minimal bp5-icon-document-open'
        to='/orders'
      >
        {t('menu.exerciseOrders')}
      </Link>
      <Link
        role='button'
        className='bp5-button bp5-minimal bp5-icon-label'
        to='/logs'
      >
        {t('menu.logs')}
      </Link>
    </>
  );
};

export default ManagerNavbarLinks;
