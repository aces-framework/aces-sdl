import {
  Button,
  Classes,
  Dialog,
  DialogBody,
  DialogFooter,
  H2,
} from '@blueprintjs/core';
import React, {useEffect} from 'react';
import {useFieldArray, useForm} from 'react-hook-form';
import {useTranslation} from 'react-i18next';
import DialogNumericInput from 'src/components/Form/DialogNumericInput';
import DialogSuggest from 'src/components/Form/DialogSuggest';
import DialogTextArea from 'src/components/Form/DialogTextArea';
import DialogTextInput from 'src/components/Form/DialogTextInput';
import {type NewEnvironment, type Environment} from 'src/models/order';

const EnvironmentDialog = (
  {
    isOpen,
    crossClicked,
    onSubmit,
    editableEnvironment,
  }: {
    isOpen: boolean;
    crossClicked: () => void;
    onSubmit: (formContent: NewEnvironment) => void;
    editableEnvironment?: Environment;
  },
) => {
  const {t} = useTranslation();

  const {handleSubmit, control, reset} = useForm<NewEnvironment>({
    defaultValues: {
      name: '',
      category: '',
      additionalInformation: '',
      size: 1,
      weaknesses: [],
      strengths: [],
    },
  });

  useEffect(() => {
    reset({
      name: editableEnvironment?.name ?? '',
      category: editableEnvironment?.category ?? '',
      size: editableEnvironment?.size ?? 1,
      additionalInformation: editableEnvironment?.additionalInformation ?? '',
      weaknesses: editableEnvironment?.weaknesses ?? [],
      strengths: editableEnvironment?.strengths ?? [],
    });
  }, [editableEnvironment, reset]);

  const onHandleSubmit = async (formContent: NewEnvironment) => {
    onSubmit(formContent);
    reset();
  };

  const {fields: strengthFields, append: appendStrength, remove: removeStrength} = useFieldArray({
    control,
    name: 'strengths',
  });
  const {fields: weaknessFields, append: appendWeakness, remove: removeWeakness} = useFieldArray({
    control,
    name: 'weaknesses',
  });

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
          <DialogTextInput<NewEnvironment>
            controllerProps={{
              control,
              name: 'name',
              rules: {
                required: t('orders.environmentElements.nameRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.environmentElements.nameMaxLength'),
                },
              },
            }}
            id='name'
            label={t('orders.environmentElements.name')}
          />
          <DialogSuggest<NewEnvironment>
            controllerProps={{
              control,
              name: 'category',
              rules: {
                required: t('orders.environmentElements.categoryRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.environmentElements.categoryMaxLength'),
                },
              },
            }}
            id='category'
            label={t('orders.environmentElements.category')}
            items={['Office', 'SME servers']}
          />
          <DialogNumericInput<NewEnvironment>
            controllerProps={{
              control,
              name: 'size',
              rules: {
                min: 1,
              },
            }}
            id='size'
            label={t('orders.environmentElements.size')}
          />
          <DialogTextArea<NewEnvironment>
            textAreaProps={{
              fill: true,
              autoResize: true,
            }}
            controllerProps={{
              control,
              name: 'additionalInformation',
              rules: {
                maxLength: {
                  value: 3000,
                  message: t('orders.environmentElements.additionalInformationMaxLength'),
                },
              },
            }}
            id='additionalInformation'
            label={t('orders.environmentElements.additionalInformation')}
          />
          <div className='flex justify-end'>
            <div className='flex gap-2'>
              <Button
                minimal
                intent='primary'
                icon='plus'
                onClick={() => {
                  appendStrength({strength: ''});
                }}
              >
                {t('orders.environmentElements.addNewStrength')}
              </Button>
            </div>
          </div>
          {strengthFields.map((field, index) => (
            <div key={field.id} className='flex gap-6 items-end'>
              <div className='grow'>
                <DialogTextInput<NewEnvironment>
                  controllerProps={{
                    control,
                    name: `strengths.${index}.strength`,
                    rules: {
                      required: t('orders.environmentElements.strengthRequired') ?? '',
                      maxLength: {
                        value: 255,
                        message: t('orders.environmentElements.strengthMaxLength'),
                      },
                    },
                    defaultValue: '',
                  }}
                  id={`strengt.${index}`}
                  label={t('orders.environmentElements.strength')}
                />
              </div>
              <Button
                minimal
                intent='danger'
                className='shrink-0 my-6'
                icon='remove'
                onClick={() => {
                  removeStrength(index);
                }}/>
            </div>
          ))}
          <div className='flex justify-end'>
            <div className='flex gap-2'>
              <Button
                minimal
                intent='primary'
                icon='plus'
                onClick={() => {
                  appendWeakness({weakness: ''});
                }}
              >
                {t('orders.environmentElements.addNewWeakness')}
              </Button>
            </div>
          </div>
          {weaknessFields.map((field, index) => (
            <div key={field.id} className='flex gap-6 items-end'>
              <div className='grow'>
                <DialogTextInput<NewEnvironment>
                  controllerProps={{
                    control,
                    name: `weaknesses.${index}.weakness`,
                    rules: {
                      required: t('orders.environmentElements.weaknessRequired') ?? '',
                      maxLength: {
                        value: 255,
                        message: t('orders.environmentElements.weaknessMaxLength'),
                      },
                    },
                    defaultValue: '',
                  }}
                  id={`weakness.${index}`}
                  label={t('orders.environmentElements.weakness')}
                />
              </div>
              <Button
                minimal
                intent='danger'
                className='shrink-0 my-6'
                icon='remove'
                onClick={() => {
                  removeWeakness(index);
                }}/>
            </div>
          ))}
        </DialogBody>
        <DialogFooter
          actions={<Button intent='primary' type='submit' text={t('orders.submit')}/>}
        />
      </form>
    </Dialog>
  );
};

export default EnvironmentDialog;

