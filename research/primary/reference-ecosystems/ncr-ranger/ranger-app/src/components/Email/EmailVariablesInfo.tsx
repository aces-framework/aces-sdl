import React from 'react';
import {Button, Tooltip} from '@blueprintjs/core';
import {type EmailVariable} from 'src/models/email';
import {useTranslation} from 'react-i18next';

const EmailVariablesInfo = ({emailVariables}: {emailVariables: EmailVariable[]}) => {
  const {t} = useTranslation();
  return (
    <Tooltip
      content={
        <div>
          <strong>{t('emails.variables.available')}</strong>
          <ul>
            {emailVariables.map(variable => (
              <li key={variable.name}>{variable.name} - {variable.description}</li>
            ))}
          </ul>
        </div>
      }
    >
      <Button minimal icon='info-sign'/>
    </Tooltip>
  );
};

export default EmailVariablesInfo;
