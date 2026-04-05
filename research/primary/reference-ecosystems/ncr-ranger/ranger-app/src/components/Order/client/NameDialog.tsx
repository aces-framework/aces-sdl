import React, {useState} from 'react';
import {Button, Dialog, H2, InputGroup} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';

const NameDialog = (
  {isOpen, title, placeholder, onSubmit, onCancel}:
  {
    isOpen?: boolean;
    title: string;
    placeholder?: string;
    onSubmit?: (name: string) => void;
    onCancel?: () => void;
  },
) => {
  const {t} = useTranslation();
  const [name, setName] = useState('');

  if (isOpen !== undefined && onSubmit && onCancel) {
    return (
      <Dialog isOpen={isOpen}>
        <div className='bp5-dialog-header'>
          <H2>{title}</H2>
          <Button
            small
            minimal
            icon='cross'
            onClick={() => {
              onCancel();
            }}/>
        </div>
        <div className='bp5-dialog-body'>
          <InputGroup
            autoFocus
            large
            value={name}
            leftIcon='graph'
            placeholder={placeholder ?? 'Name'}
            onChange={event => {
              setName(event.target.value);
            }}/>
        </div>
        <div className='bp5-dialog-footer'>
          <div className='bp5-dialog-footer-actions'>
            <Button
              large
              intent='primary'
              text={t('common.add')}
              onClick={() => {
                if (name !== '') {
                  onSubmit(name);
                  setName('');
                }
              }}/>
          </div>
        </div>
      </Dialog>
    );
  }

  return null;
};

export default NameDialog;
