import type { NextPage } from 'next';
import { Button, H3 } from '@blueprintjs/core';
import useTranslation from 'next-translate/useTranslation';
import { useRouter } from 'next/router';

const Home: NextPage = () => {
  const { t } = useTranslation('common');
  const router = useRouter();
  const handleClickDoc = (event: React.MouseEvent<HTMLElement>) => {
    event.preventDefault();

    if (process.env.DOCUMENTATION_URL) {
      router.push(process.env.DOCUMENTATION_URL);
    }
  };
  const handleClickInstaller = (event: React.MouseEvent<HTMLElement>) => {
    event.preventDefault();

    if (process.env.INSTALLER_URL) {
      router.push(process.env.INSTALLER_URL);
    }
  };

  return (
    <div className="flex flex-col items-center p-4 mt-4 md:p-10 md:mt-6">
      <H3 className="text-lg text-center md:text-2xl">{t('welcome')}</H3>
      <div className="flex flex-col md:flex-row mt-6 space-y-4 md:space-y-0 md:space-x-4">
        <Button intent="primary" large onClick={handleClickInstaller}>
          {t('installerButton')}
        </Button>
        <Button intent="primary" large onClick={handleClickDoc}>
          {t('documentationButton')}
        </Button>
      </div>
    </div>
  );
};

export default Home;
