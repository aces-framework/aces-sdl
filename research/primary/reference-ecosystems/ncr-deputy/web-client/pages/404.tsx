import React from 'react';
import Link from 'next/link';
import useTranslation from 'next-translate/useTranslation';

const Custom404 = () => {
  const { t } = useTranslation('common');

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <h1 className="text-4xl font-bold mb-4">{t('404.title')}</h1>
      <p className="text-lg mb-6">{t('404.description')}</p>
      <Link className="text-blue-500 hover:underline" href="/">
        {t('404.backToHome')}
      </Link>
    </div>
  );
};

export default Custom404;
