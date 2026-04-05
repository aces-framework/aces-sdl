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
import DialogTextInput from 'src/components/Form/DialogTextInput';
import {
  type TrainingObjective,
  type NewTrainingObjective,
} from 'src/models/order';

const TrainingObjectiveDialog = (
  {
    isOpen,
    crossClicked,
    onSubmit,
    editableTrainingObjective,
  }: {
    isOpen: boolean;
    crossClicked: () => void;
    onSubmit: (formContent: NewTrainingObjective) => void;
    editableTrainingObjective?: TrainingObjective;
  },
) => {
  const {t} = useTranslation();

  const {handleSubmit, control, reset} = useForm<NewTrainingObjective>({
    defaultValues: {
      objective: '',
      threats: [{
        threat: '',
      }],
    },
  });

  useEffect(() => {
    reset({
      objective: editableTrainingObjective?.objective ?? '',
      threats: editableTrainingObjective?.threats ?? [{
        threat: '',
      }],
    });
  }, [editableTrainingObjective, reset]);

  const onHandleSubmit = async (formContent: NewTrainingObjective) => {
    onSubmit(formContent);
    reset();
  };

  const {fields, append, remove} = useFieldArray({
    control,
    name: 'threats',
  });

  return (
    <Dialog
      isOpen={isOpen}
    >
      <div className={Classes.DIALOG_HEADER}>
        <H2>{t('orders.trainingObjective.add')}</H2>
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
          <DialogTextInput<NewTrainingObjective>
            controllerProps={{
              control,
              name: 'objective',
              rules: {
                required: t('orders.trainingObjective.objectiveRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.trainingObjective.objectiveMaxLength'),
                },
              },
            }}
            id='objective'
            label={t('orders.trainingObjective.objective')}
          />
          <div className='flex justify-end'>
            <div className='flex gap-2'>
              <Button
                minimal
                intent='primary'
                icon='plus'
                onClick={() => {
                  append({threat: ''});
                }}
              >
                {t('orders.trainingObjective.addNewThreat')}
              </Button>
            </div>
          </div>
          {fields.map((field, index) => (
            <div key={field.id} className='flex gap-6 items-end'>
              <div className='grow'>
                <DialogTextInput<NewTrainingObjective>
                  controllerProps={{
                    control,
                    name: `threats.${index}.threat`,
                    rules: {
                      required: t('orders.trainingObjective.threatRequired') ?? '',
                      maxLength: {
                        value: 255,
                        message: t('orders.threatMaxLength.maxLength'),
                      },
                    },
                    defaultValue: '',
                  }}
                  id={`threats.${index}`}
                  label={t('orders.trainingObjective.threat')}
                />
              </div>
              <Button
                minimal
                intent='danger'
                className='shrink-0 my-6'
                icon='remove'
                onClick={() => {
                  remove(index);
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

export default TrainingObjectiveDialog;

