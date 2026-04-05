import React from 'react';
import {useTranslation} from 'react-i18next';
import HomeView from 'src/components/HomeView';

const Home = () => {
  const {t} = useTranslation();

  return (
    <HomeView
      buttonText={t('menu.exercises')}
      buttonLink='/exercises'/>
  );
};

export default Home;
