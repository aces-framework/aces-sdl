import type { AppProps } from 'next/app';
import '@blueprintjs/core/lib/css/blueprint.css';
import '../styles/global.css';
import Head from 'next/head';
import useTranslation from 'next-translate/useTranslation';
import React from 'react';
import { SessionProvider } from 'next-auth/react';
import MainNavbar from '../components/MainNavbar';
import SessionCheck from '../components/SessionCheck';

if (typeof window === 'undefined') React.useLayoutEffect = React.useEffect;

const Deputy = ({
  Component,
  pageProps: { session, ...pageProps },
}: AppProps) => {
  const { t } = useTranslation('common');

  return (
    <SessionProvider
      refetchInterval={60}
      refetchOnWindowFocus
      session={session}
    >
      <Head>
        <link rel="icon" href="/favicon.ico" />
        <title>{t('title')}</title>
        <meta name={t('metaName')} content={t('metaContent')} />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      </Head>

      <MainNavbar />
      <SessionCheck>
        <div className="flex flex-col items-center min-h-screen p-4 md:p-10">
          <Component {...pageProps} />
        </div>
      </SessionCheck>
    </SessionProvider>
  );
};

export default Deputy;
