import {
  Button,
  Classes,
  Dialog,
  DialogBody,
  DialogFooter,
  FileInput,
  FormGroup,
  H2,
} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import {useForm} from 'react-hook-form';
import {useTranslation} from 'react-i18next';
import {useSelector} from 'react-redux';
import DialogSelect from 'src/components/Form/DialogSelect';
import DialogTextArea from 'src/components/Form/DialogTextArea';
import DialogTextInput from 'src/components/Form/DialogTextInput';
import {toastWarning} from 'src/components/Toaster';
import {BASE_URL} from 'src/constants';
import {
  type Order,
  type CustomElement,
  type NewCustomElement,
} from 'src/models/order';
import {tokenSelector} from 'src/slices/userSlice';
import {dowloadFile} from 'src/utils';

const orderBase = `${BASE_URL}/client/order`;

const CustomElementDialog = (
  {
    isOpen,
    crossClicked,
    onSubmit,
    editableCustomElement,
    order,
  }: {
    isOpen: boolean;
    crossClicked: () => void;
    onSubmit: (formContent: NewCustomElement, file: File | undefined) => void;
    editableCustomElement?: CustomElement;
    order: Order;
  },
) => {
  const {t} = useTranslation();

  const fileMessage = editableCustomElement
    ? t('orders.customElement.updateFile') : t('orders.customElement.addFile');
  const [fileText, setFileText] = useState(fileMessage ?? '');
  const [currentFile, setCurrentFile] = useState<File | undefined>();
  const [fileInputError, setFileInputError] = useState<string | undefined>();
  const [fileLink, setFileLink] = useState<string | undefined>();
  const token = useSelector(tokenSelector);

  const {handleSubmit, control, reset} = useForm<NewCustomElement>({
    defaultValues: {
      name: '',
      description: '',
      environmentId: '',
    },
  });

  useEffect(() => {
    reset({
      name: editableCustomElement?.name ?? '',
      description: editableCustomElement?.description ?? '',
      environmentId: editableCustomElement?.environmentId ?? '',
    });
    setFileInputError(undefined);
  }, [editableCustomElement, reset, fileMessage]);

  useEffect(() => {
    setFileText(fileMessage);
  }
  , [fileMessage]);

  useEffect(() => {
    if (editableCustomElement) {
      setFileLink(`${orderBase}/${order.id}/custom_element/${editableCustomElement.id}/file`);
    }
  }
  , [editableCustomElement, order.id]);

  const onHandleSubmit = async (formContent: NewCustomElement) => {
    if (!editableCustomElement && currentFile === undefined) {
      setFileInputError(t('orders.customElement.fileRequired') ?? '');
    } else if (currentFile !== undefined && !(currentFile?.name.endsWith('.zip'))) {
      setFileInputError(t('orders.customElement.zipFileRequired') ?? '');
    } else {
      onSubmit(formContent, currentFile);
      reset();
    }
  };

  const environmentExists = order.environments && order.environments?.length > 0;
  return (
    <Dialog
      isOpen={isOpen}
    >
      <div className={Classes.DIALOG_HEADER}>
        <H2>{t('orders.environmentElements.add')}</H2>
        <Button
          small
          minimal
          icon='cross'
          onClick={() => {
            crossClicked();
          }}/>
      </div>
      <form onSubmit={handleSubmit(onHandleSubmit)}>
        <DialogBody>
          <DialogTextInput<NewCustomElement>
            controllerProps={{
              control,
              name: 'name',
              rules: {
                required: t('orders.customElement.nameRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.customElement.nameMaxLength'),
                },
              },
            }}
            id='name'
            label={t('orders.customElement.name')}
          />
          <DialogTextArea<NewCustomElement>
            textAreaProps={{
              fill: true,
              autoResize: true,
            }}
            controllerProps={{
              control,
              name: 'description',
              rules: {
                maxLength: {
                  value: 3000,
                  message: t('orders.customElement.descriptionMaxLength'),
                },
              },
            }}
            id='description'
            label={t('orders.customElement.description')}
          />
          <DialogSelect<NewCustomElement>
            selectProps={{
              disabled: !environmentExists,
              fill: true,
              options: environmentExists ? [
                {
                  label: t('orders.customElement.noEnvironment') ?? '',
                  value: '',
                },
                ...(order.environments?.map(environment => ({
                  label: environment.name,
                  value: environment.id,
                })) ?? []),
              ] : [{
                label: t('orders.customElement.noPossibleEnvironments') ?? '',
                value: '',
              }],
            }}
            controllerProps={{
              control,
              name: 'environmentId',
              rules: {
                required: t('orders.customElement.environmentRequired') ?? '',
              },
            }}
            id='environmentId'
            label={t('orders.customElement.environment')}
          />
          {editableCustomElement && (
            <Button
              large
              intent='primary'
              onClick={async () => {
                await dowloadFile(
                  fileLink ?? '',
                  token ?? '',
                  `${editableCustomElement.name}.zip`,
                  () => {
                    toastWarning(t('orders.customElement.failedToDownloadFile'));
                  });
              }}
            >
              {t('orders.customElement.downloadCurrentFile')}
            </Button>
          )}
          <FormGroup
            className='mt-2'
            label={t('orders.customElement.file')}
            intent='danger'
            helperText={fileInputError}
          >
            <FileInput
              large
              fill
              text={fileText}
              buttonText={t('orders.customElement.browse') ?? ''}
              onInputChange={input => {
                if (input.target) {
                  const file = (input.target as HTMLInputElement).files?.[0];
                  if (file) {
                    setFileText(file.name);
                    setCurrentFile(file);
                  }
                }
              }}/>
          </FormGroup>
        </DialogBody>
        <DialogFooter
          actions={<Button intent='primary' type='submit' text={t('orders.submit')}/>}
        />
      </form>
    </Dialog>
  );
};

export default CustomElementDialog;

