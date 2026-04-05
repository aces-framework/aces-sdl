import {FormGroup, HTMLSelect, Intent} from '@blueprintjs/core';
import type React from 'react';
import {Controller, type FieldValues} from 'react-hook-form';
import {useTranslation} from 'react-i18next';

const DialogSelect = <T extends FieldValues>({
  controllerProps,
  id,
  label,
  selectProps,
}: {
  controllerProps: Omit<React.ComponentProps<typeof Controller<T>>, 'render'>;
  selectProps?: Omit<React.ComponentProps<typeof HTMLSelect>, 'value' | 'onChange'>;
  id: string;
  label: string;
}) => {
  const {t} = useTranslation();

  return (
    <Controller
      {...controllerProps}
      render={({
        field: {onChange, onBlur, value}, fieldState: {error},
      }) => {
        const intent = error ? Intent.DANGER : Intent.NONE;
        const realValue = value ?? '';
        if (typeof realValue !== 'string') {
          throw new TypeError('TextInput value must be a string');
        }

        return (
          <FormGroup
            labelFor={id}
            labelInfo={controllerProps.rules?.required === true ? t('common.required') : ''}
            helperText={error?.message ?? ''}
            intent={intent}
            label={label}
          >
            <HTMLSelect
              {...(selectProps ?? {})}
              large
              value={realValue}
              id={id}
              onChange={onChange}
              onBlur={onBlur}
            />
          </FormGroup>
        );
      }}
    />
  );
};

export default DialogSelect;

