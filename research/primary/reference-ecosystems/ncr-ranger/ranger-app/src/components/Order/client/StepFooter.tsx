import {Button} from '@blueprintjs/core';
import React from 'react';
import {useTranslation} from 'react-i18next';
import {useNavigate} from 'react-router-dom';
import {type FormType} from 'src/models/routes';

const formTypes: FormType[] = [
  'training-objectives',
  'structure',
  'environment',
  'custom-elements',
  'plot',
  'final',
];

const getNextFormType = (formType: FormType) => {
  const currentIndex = formTypes.indexOf(formType);
  if (currentIndex === -1 || currentIndex === formTypes.length - 1) {
    return undefined;
  }

  return formTypes[currentIndex + 1];
};

const getPreviousFormType = (formType: FormType) => {
  const currentIndex = formTypes.indexOf(formType);
  if (currentIndex === -1 || currentIndex === 0) {
    return undefined;
  }

  return formTypes[currentIndex - 1];
};

const StepFooter = (
  {
    stage: formType,
    orderId,
    isUserClient,
    onSubmit,
    readyForNext,
  }: {
    stage: FormType;
    orderId: string;
    isUserClient: boolean;
    onSubmit: () => void;
    readyForNext: boolean;
  }) => {
  const {t} = useTranslation();

  const navigate = useNavigate();

  return (
    <div className='flex justify-between'>
      {formType === 'training-objectives' ? <span/>
        : (
          <Button
            large
            intent='primary'
            onClick={() => {
              const nextFormType = getPreviousFormType(formType);
              if (nextFormType) {
                navigate(`/orders/${orderId}/${nextFormType}`);
              }
            }}
          >{t('orders.back')}
          </Button>
        )}
      {formType === 'final' ? (
        <Button
          large
          disabled={!isUserClient}
          intent='success'
          onClick={() => {
            onSubmit();
          }}
        >{t('orders.submit')}
        </Button>
      )
        : (
          <Button
            large
            disabled={!readyForNext}
            intent='primary'
            onClick={() => {
              const nextFormType = getNextFormType(formType);
              if (nextFormType) {
                navigate(`/orders/${orderId}/${nextFormType}`);
              }
            }}
          >{t('orders.next')}
          </Button>
        )}
    </div>
  );
};

export default StepFooter;
