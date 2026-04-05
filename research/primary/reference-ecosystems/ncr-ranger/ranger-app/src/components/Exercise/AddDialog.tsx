import React from 'react';
import {
  Button,
  Dialog,
  FormGroup,
  H2,
  HTMLSelect,
  InputGroup,
  Intent,
} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import {
  useAdminGetDefaultDeploymentGroupQuery,
  useAdminGetDeploymentGroupsQuery,
} from 'src/slices/apiSlice';
import {type NewExercise} from 'src/models/exercise';
import {Controller, useForm} from 'react-hook-form';

const AddDialog = (
  {isOpen, title, onSubmit, onCancel}:
  {
    isOpen?: boolean;
    title: string;
    onSubmit?: ({name, deploymentGroup}: NewExercise) => void;
    onCancel?: () => void;
  },
) => {
  const {t} = useTranslation();
  const {data: deploymentGroups} = useAdminGetDeploymentGroupsQuery();
  const {data: defaultDeploymentGroup} = useAdminGetDefaultDeploymentGroupQuery();
  const {handleSubmit, control} = useForm<NewExercise>({
    defaultValues: {
      name: '',
      deploymentGroup: defaultDeploymentGroup,
    },
  });

  const onHandleSubmit = (formContent: NewExercise) => {
    if (onSubmit) {
      onSubmit(formContent);
    }
  };

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
        <form onSubmit={handleSubmit(onHandleSubmit)}>
          <div className='bp5-dialog-body'>
            <Controller
              control={control}
              name='name'
              rules={{required: t('exercises.mustHaveName') ?? ''}}
              render={({
                field: {onChange, value}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                return (
                  <FormGroup
                    labelFor='exercise-name'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('exercises.name')}
                  >
                    <InputGroup
                      autoFocus
                      large
                      id='exercise-name'
                      intent={intent}
                      value={value}
                      leftIcon='graph'
                      placeholder={t('exercises.name') ?? ''}
                      onChange={onChange}/>
                  </FormGroup>
                );
              }}
            />

            <Controller
              control={control}
              name='deploymentGroup'
              defaultValue={defaultDeploymentGroup}
              render={({
                field: {onChange, value},
              }) => (
                <FormGroup
                  labelFor='deployment-group'
                  labelInfo='(required)'
                  label={t('exercises.group.title')}
                >
                  <HTMLSelect
                    large
                    fill
                    id='deployment-group'
                    value={value}
                    onChange={onChange}
                  >
                    {Object.keys((deploymentGroups ?? {})).map(groupName =>
                      <option key={groupName}>{groupName}</option>)}
                  </HTMLSelect>
                </FormGroup>
              )}
            />
          </div>
          <div className='bp5-dialog-footer'>
            <div className='bp5-dialog-footer-actions'>
              <Button
                large
                type='submit'
                intent='primary'
                text={t('common.add')}
              />
            </div>
          </div>
        </form>
      </Dialog>
    );
  }

  return null;
};

export default AddDialog;
