import React from 'react';
import {useTranslation} from 'react-i18next';
import HomeView from 'src/components/HomeView';

const Home = () => {
  const {t} = useTranslation();

  return (
    <HomeView
      buttonText={t('documentation')}
      // eslint-disable-next-line max-len
      buttonLink='https://documentation.opencyberrange.ee/docs/ranger/user_guides/manager-user-guide'/>
  );
};

export default Home;
