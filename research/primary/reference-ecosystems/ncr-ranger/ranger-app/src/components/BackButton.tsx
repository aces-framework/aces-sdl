import React from 'react';
import {useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {Button} from '@blueprintjs/core';

const BackButton = () => {
  const {t} = useTranslation();
  const navigate = useNavigate();

  return (
    <Button
      icon='arrow-left'
      intent='primary'
      onClick={() => {
        navigate(-1);
      }}
    >{t('common.back')}
    </Button>
  );
};

export default BackButton;
