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
import DialogSelect from 'src/components/Form/DialogSelect';
import DialogTextArea from 'src/components/Form/DialogTextArea';
import DialogTextInput from 'src/components/Form/DialogTextInput';
import DialogMultiSelect from 'src/components/Form/DialogMultiSelect';
import {type Order, type NewStructure, type Structure} from 'src/models/order';

const StructureDialog = (
  {
    isOpen,
    crossClicked,
    onSubmit,
    editableStructure,
    order,
  }: {
    isOpen: boolean;
    crossClicked: () => void;
    onSubmit: (formContent: NewStructure) => void;
    editableStructure?: Structure;
    order: Order;
  },
) => {
  const {t} = useTranslation();

  const {handleSubmit, control, reset} = useForm<NewStructure>({
    defaultValues: {
      name: '',
      description: '',
      parentId: undefined,
      skills: [],
      weaknesses: [],
      trainingObjectiveIds: [],
    },
  });

  useEffect(() => {
    reset({
      name: editableStructure?.name ?? '',
      description: editableStructure?.description ?? '',
      parentId: editableStructure?.parentId ?? '',
      skills: editableStructure?.skills ?? [],
      weaknesses: editableStructure?.weaknesses ?? [],
      trainingObjectiveIds: editableStructure?.trainingObjectiveIds ?? [],
    });
  }, [editableStructure, reset]);

  const onHandleSubmit = async (formContent: NewStructure) => {
    const newStructure = {
      ...formContent,
      parentId: formContent.parentId === '' ? undefined : formContent.parentId,
    };
    onSubmit(newStructure);
    reset();
  };

  const {fields: skillFields, append: appendSkill, remove: removeSkill} = useFieldArray({
    control,
    name: 'skills',
  });
  const {fields: weaknessFields, append: appendWeakness, remove: removeWeakness} = useFieldArray({
    control,
    name: 'weaknesses',
  });

  const structuresExist = order.structures && order.structures.length > 0;
  return (
    <Dialog
      isOpen={isOpen}
    >
      <div className={Classes.DIALOG_HEADER}>
        <H2>{t('orders.structureElements.add')}</H2>
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
          <DialogTextInput<NewStructure>
            controllerProps={{
              control,
              name: 'name',
              rules: {
                required: t('orders.structureElements.nameRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.structureElements.nameMaxLength'),
                },
              },
            }}
            id='name'
            label={t('orders.structureElements.name')}
          />
          <DialogTextArea<NewStructure>
            textAreaProps={{
              fill: true,
              autoResize: true,
            }}
            controllerProps={{
              control,
              name: 'description',
              rules: {
                required: t('orders.structureElements.descriptionRequired') ?? '',
                maxLength: {
                  value: 3000,
                  message: t('orders.structureElements.descriptionMaxLength'),
                },
              },
            }}
            id='description'
            label={t('orders.structureElements.description')}
          />
          <DialogSelect<NewStructure>
            selectProps={{
              disabled: !structuresExist,
              fill: true,
              options: structuresExist ? [
                {
                  label: t('orders.structureElements.noParent') ?? '',
                  value: '',
                },
                ...(order.structures?.map(structure => ({
                  label: structure.name,
                  value: structure.id,
                })) ?? []),
              ] : [{
                label: t('orders.structureElements.noPossibleParents') ?? '',
                value: '',
              }],
            }}
            controllerProps={{
              control,
              name: 'parentId',
            }}
            id='parentId'
            label={t('orders.structureElements.parent')}
          />
          <div className='flex justify-end'>
            <div className='flex gap-2'>
              <Button
                minimal
                intent='primary'
                icon='plus'
                onClick={() => {
                  appendSkill({skill: ''});
                }}
              >
                {t('orders.structureElements.addNewSkill')}
              </Button>
            </div>
          </div>
          {skillFields.map((field, index) => (
            <div key={field.id} className='flex gap-6 items-end'>
              <div className='grow'>
                <DialogTextInput<NewStructure>
                  controllerProps={{
                    control,
                    name: `skills.${index}.skill`,
                    rules: {
                      required: t('orders.structureElements.skillRequired') ?? '',
                      maxLength: {
                        value: 255,
                        message: t('orders.structureElements.skillMaxLength'),
                      },
                    },
                    defaultValue: '',
                  }}
                  id={`skill.${index}`}
                  label={t('orders.structureElements.skill')}
                />
              </div>
              <Button
                minimal
                intent='danger'
                className='shrink-0 my-6'
                icon='remove'
                onClick={() => {
                  removeSkill(index);
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
                {t('orders.structureElements.addNewWeakness')}
              </Button>
            </div>
          </div>
          {weaknessFields.map((field, index) => (
            <div key={field.id} className='flex gap-6 items-end'>
              <div className='grow'>
                <DialogTextInput<NewStructure>
                  controllerProps={{
                    control,
                    name: `weaknesses.${index}.weakness`,
                    rules: {
                      required: t('orders.structureElements.weaknessRequired') ?? '',
                      maxLength: {
                        value: 255,
                        message: t('orders.structureElements.weaknessMaxLength'),
                      },
                    },
                    defaultValue: '',
                  }}
                  id={`weakness.${index}`}
                  label={t('orders.structureElements.weakness')}
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
          <div>
            <DialogMultiSelect<NewStructure, 'trainingObjectiveIds', 'trainingObjectiveId'>
              control={control}
              items={(order.trainingObjectives ?? []).map(trainingObjective => ({
                trainingObjectiveId: trainingObjective.id,
              }))}
              name='trainingObjectiveIds'
              keyName='trainingObjectiveId'
              textRenderer={item => {
                const trainingObjective = (order.trainingObjectives ?? []).find(
                  trainingObjective => trainingObjective.id === item.trainingObjectiveId,
                );
                return trainingObjective?.objective ?? '';
              }}
              id='trainingObjectiveIds'
              label={t('orders.structureElements.connectedTrainingObjectives')}
            />
          </div>
        </DialogBody>
        <DialogFooter
          actions={<Button intent='primary' type='submit' text={t('orders.submit')}/>}
        />
      </form>
    </Dialog>
  );
};

export default StructureDialog;

