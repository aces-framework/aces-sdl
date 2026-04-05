import type React from 'react';
import type {DeploymentForm} from 'src/models/deployment';
import {
  Button,
  Dialog,
  H2,
  InputGroup,
  FormGroup,
  Classes,
  Intent,
  NumericInput,
  MenuItem,
} from '@blueprintjs/core';
import {useAdminGetGroupsQuery} from 'src/slices/apiSlice';
import {useTranslation} from 'react-i18next';
import {Controller, useFieldArray, useForm, useWatch} from 'react-hook-form';
import {Suggest} from '@blueprintjs/select';
import {type AdGroup} from 'src/models/groups';
import DatePicker from 'react-datepicker';
import {useEffect, useState} from 'react';

const AddDialog = (
  {isOpen, title, deploymentGroup, onSubmit, onCancel}:
  {
    title: string;
    isOpen: boolean;
    deploymentGroup: string;
    onSubmit: ({
      count,
      name,
      deploymentGroup,
      groupNames,
      start,
      end,
    }: DeploymentForm) => void;
    onCancel: () => void;
  },
) => {
  const {t} = useTranslation();
  const {data: groups} = useAdminGetGroupsQuery();
  const [startDate, setStartDate] = useState<Date | undefined>(undefined);
  const [endDate, setEndDate] = useState<Date | undefined>(undefined);
  const {handleSubmit, control} = useForm<DeploymentForm>({
    defaultValues: {
      name: '',
      deploymentGroup,
      groupNames: [],
      count: 1,
      start: undefined,
      end: undefined,
    },
  });
  const count = useWatch({control, name: 'count', defaultValue: 1});
  const {fields, append, remove} = useFieldArray({
    control,
    name: 'groupNames',
  });
  useEffect(() => {
    let added = 0;
    while (fields.length + added < count) {
      append({groupName: ''});
      added += 1;
    }

    let removed = 0;
    while (fields.length - removed > count) {
      remove(fields.length - 1);
      removed += 1;
    }
  }, [count, append, remove, fields.length]);

  const onHandleSubmit = (formContent: DeploymentForm) => {
    if (onSubmit) {
      formContent.start = formContent.start.slice(0, -5);
      formContent.end = formContent.end.slice(0, -5);
      onSubmit(formContent);
    }
  };

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
            }}/>
        </div>
        <form onSubmit={handleSubmit(onHandleSubmit)}>
          <div className={Classes.DIALOG_BODY}>
            <FormGroup
              label={t('exercises.group.title')}
            >
              <InputGroup
                large
                disabled
                placeholder={deploymentGroup ?? ''}
              />
            </FormGroup>
            <Controller
              control={control}
              name='name'
              rules={{required: t('deployments.form.name.required') ?? ''}}
              render={({
                field: {onChange, onBlur, ref, value}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                return (
                  <FormGroup
                    labelFor='deployment-name'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('deployments.form.name.title')}
                  >
                    <InputGroup
                      large
                      intent={intent}
                      value={value}
                      inputRef={ref}
                      id='deployment-name'
                      onChange={onChange}
                      onBlur={onBlur}
                    />
                  </FormGroup>
                );
              }}
            />
            <Controller
              control={control}
              name='start'
              rules={{required: t('deployments.form.startDate.required') ?? ''}}
              render={({
                field: {onChange, onBlur}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                return (
                  <FormGroup
                    labelFor='start-date'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('deployments.form.startDate.title')}
                  >
                    <div className='flex flex-col'>
                      <DatePicker
                        selectsStart
                        showTimeSelect
                        customInput={<input className='bp5-input bp5-large bp5-fill'/>}
                        id='start-date'
                        selected={startDate}
                        startDate={startDate}
                        endDate={endDate}
                        timeFormat='HH:mm'
                        dateFormat='dd/MM/yyyy HH:mm'
                        onChange={date => {
                          setStartDate(date ?? undefined);
                          onChange(date?.toISOString() ?? '');
                        }}
                        onBlur={onBlur}
                      />
                    </div>
                  </FormGroup>
                );
              }}
            />
            <Controller
              control={control}
              name='end'
              rules={{
                required: t('deployments.form.endDate.required') ?? '',
                validate: {
                  endDateAfterStartDate: (value: string) =>
                    !startDate || !value || new Date(value) > new Date(startDate)
                    || (t('deployments.form.endDate.earlierThanStart') ?? ''),
                },
              }}
              render={({
                field: {onChange, onBlur}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                const filterFromStart = (time: Date) => {
                  if (startDate) {
                    return time > startDate;
                  }

                  return true;
                };

                return (
                  <FormGroup
                    labelFor='end-date'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('deployments.form.endDate.title')}
                  >
                    <div className='flex flex-col'>
                      <DatePicker
                        selectsEnd
                        showTimeSelect
                        customInput={<input className='bp5-input bp5-large bp5-fill'/>}
                        id='end-date'
                        selected={endDate}
                        startDate={startDate}
                        endDate={endDate}
                        minDate={startDate}
                        timeFormat='HH:mm'
                        dateFormat='dd/MM/yyyy HH:mm'
                        filterTime={filterFromStart}
                        onChange={date => {
                          setEndDate(date ?? undefined);
                          onChange(date?.toISOString() ?? '');
                        }}
                        onBlur={onBlur}
                      />
                    </div>
                  </FormGroup>
                );
              }}
            />
            <Controller
              control={control}
              name='count'
              rules={{required: t('deployments.form.count.required') ?? ''}}
              render={({
                field: {onChange, onBlur, ref, value}, fieldState: {error},
              }) => {
                const intent = error ? Intent.DANGER : Intent.NONE;
                return (
                  <FormGroup
                    labelFor='deployment-count'
                    labelInfo='(required)'
                    helperText={error?.message}
                    intent={intent}
                    label={t('deployments.form.count.title')}
                  >
                    <NumericInput
                      fill
                      large
                      buttonPosition='none'
                      max={200}
                      min={1}
                      intent={intent}
                      value={value}
                      inputRef={ref}
                      id='deployment-count'
                      onValueChange={onChange}
                      onBlur={onBlur}
                    />
                  </FormGroup>
                );
              }}
            />
            {fields.map((field, index) => (
              <Controller
                key={field.id}
                control={control}
                name={`groupNames.${index}.groupName`}
                rules={{required: true}}
                render={({
                  field: {onBlur, ref, value, onChange}, fieldState: {error},
                }) => {
                  const intent = error ? Intent.DANGER : Intent.NONE;
                  const activeItem = groups?.find(group => group.name === value);
                  return (
                    <FormGroup
                      labelFor='group-name'
                      labelInfo='(required)'
                      helperText={error?.message}
                      intent={intent}
                      label={t('deployments.form.adGroups.title', {number: index + 1})}
                    >
                      <Suggest<AdGroup>
                        inputProps={{
                          id: 'group-name',
                          onBlur,
                          inputRef: ref,
                          placeholder: t('common.searchPlaceholder') ?? '',
                        }}
                        activeItem={activeItem}
                        inputValueRenderer={item => item.name}
                        itemPredicate={(query, item) =>
                          item.name.toLowerCase().includes(query.toLowerCase())}
                        itemRenderer={(item, {handleClick, handleFocus}) => (
                          <MenuItem
                            key={item.id}
                            text={item.name}
                            onClick={handleClick}
                            onFocus={handleFocus}
                          />
                        )}
                        items={groups ?? []}
                        noResults={
                          <MenuItem
                            disabled
                            text={t('common.noResults')}
                            roleStructure='listoption'/>
                        }
                        onItemSelect={item => {
                          onChange(item.name);
                        }}
                      />
                    </FormGroup>
                  );
                }}
              />
            ),
            )}
          </div>
          <div className={Classes.DIALOG_FOOTER}>
            <div className={Classes.DIALOG_FOOTER_ACTIONS}>
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
