import {Callout, H5} from '@blueprintjs/core';
import React from 'react';
import {useTranslation} from 'react-i18next';
import notFound from 'src/assets/404.svg';
import PageHolder from 'src/components/PageHolder';

const RolesFallback = () => {
  const {t} = useTranslation();

  return (
    <PageHolder>
      <Callout className='mt-8' intent='warning'>
        <H5>{t('fallback.notFound')}</H5>
      </Callout>
      <img
        className='h-96 md:h-max mt-24 object-cover pointer-events-none'
        src={notFound}
        alt='lost cowboy'/>
    </PageHolder>
  );
};

export default RolesFallback;
