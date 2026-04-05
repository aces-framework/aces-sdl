import {useTranslation} from 'react-i18next';
import React, {useEffect} from 'react';
import {Controller, useForm} from 'react-hook-form';
import {
  Button,
  Classes,
  Dialog,
  FormGroup,
  H2,
  InputGroup,
  Intent,
} from '@blueprintjs/core';
import {type EmailTemplateForm} from 'src/models/email';

const TemplateSaveDialog = (
  {isOpen, title, onSubmit, onCancel}:
  {
    title: string;
    isOpen: boolean;
    onSubmit: ({name}: {name: string}) => void;
    onCancel: () => void;
  },
) => {
  const {t} = useTranslation();

  const {handleSubmit, control, register}
    = useForm<EmailTemplateForm>({
      defaultValues: {
        name: '',
      },
    });

  const onHandleSubmit = (formContent: {name: string}) => {
    if (onSubmit) {
      onSubmit(formContent);
    }
  };

  useEffect(() => {
    register('name', {required: t('emails.form.templateName.required') ?? ''});
  }, [register, t]);

  if (isOpen !== undefined) {
    return (
      <Dialog isOpen={isOpen}>
        <div className={Classes.DIALOG_HEADER}>
          <H2>{title}</H2>
          <Button
            small
            minimal
            icon='cross'
            onClick={() => {
              onCancel();
            }}
          />
        </div>
        <form>
          <div className={Classes.DIALOG_BODY}>
            <Controller
              control={control}
              name='name'
              rules={{required: t('emails.form.templateName.required') ?? ''}}
              render={({
                field: {onChange, onBlur, ref, value}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                return (
                  <FormGroup
                    labelFor='template-name'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('emails.form.templateName.name')}
                  >
                    <InputGroup
                      large
                      intent={intent}
                      value={value}
                      inputRef={ref}
                      id='template-name'
                      onChange={onChange}
                      onBlur={onBlur}
                    />
                  </FormGroup>
                );
              }}
            />
          </div>
          <div className={Classes.DIALOG_FOOTER}>
            <div className={Classes.DIALOG_FOOTER_ACTIONS}>
              <Button
                large
                type='button'
                intent='primary'
                text={t('common.add')}
                onClick={handleSubmit(onHandleSubmit)}
              />
            </div>
          </div>
        </form>
      </Dialog>
    );
  }

  return null;
};

export default TemplateSaveDialog;
