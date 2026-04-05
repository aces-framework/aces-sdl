import {FormGroup, Intent} from '@blueprintjs/core';
import {DateInput3} from '@blueprintjs/datetime2';
import type React from 'react';
import {
  Controller,
  type PathValue,
  type FieldValues,
  type Path,
} from 'react-hook-form';
import {useTranslation} from 'react-i18next';

const DialogDateTimeInput = <T extends FieldValues>({
  controllerProps,
  id,
  label,
  fill,
}: {
  controllerProps: Omit<React.ComponentProps<typeof Controller<T>>, 'render'>;
  id: string;
  label: string;
  fill?: boolean;
}) => {
  const {t} = useTranslation();

  return (
    <Controller
      {...controllerProps}
      render={({
        field: {onChange, ref, value}, fieldState: {error},
      }) => {
        const intent = error ? Intent.DANGER : Intent.NONE;

        if (typeof value !== 'string') {
          throw new TypeError('TextInput value must be a string');
        }

        return (
          <FormGroup
            ref={ref}
            labelFor={id}
            labelInfo={controllerProps.rules?.required === undefined ? '' : t('common.required')}
            helperText={error?.message ?? ''}
            intent={intent}
            label={label}
          >
            <DateInput3
              dayPickerProps={{
                id,
              }}
              timePickerProps={{
                showArrowButtons: true,
              }}
              showTimezoneSelect={false}
              timePrecision='minute'
              fill={fill}
              value={value}
              onChange={value => {
                if (value !== null) {
                  const date = new Date(value);
                  onChange((date.toISOString()) as unknown as PathValue<T, Path<T>>);
                }
              }}
            />
          </FormGroup>
        );
      }}
    />
  );
};

export default DialogDateTimeInput;

