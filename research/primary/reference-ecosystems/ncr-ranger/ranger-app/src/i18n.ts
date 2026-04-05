import i18n from 'i18next';
import {initReactI18next} from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import translation from 'src/locales/en/translation';

// eslint-disable-next-line @typescript-eslint/no-floating-promises
i18n // eslint-disable-line import/no-named-as-default-member
  .use(LanguageDetector)
  .use(initReactI18next).init({
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
    resources: {
      en: {
        translation,
      },
    },
  });

export {default} from 'i18next';
