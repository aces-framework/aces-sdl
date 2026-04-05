import {FormGroup, Intent, NumericInput} from '@blueprintjs/core';
import {
  type InputSharedProps,
} from '@blueprintjs/core/lib/esm/components/forms/inputSharedProps';
import type React from 'react';
import {
  Controller,
  type PathValue,
  type FieldValues,
  type Path,
} from 'react-hook-form';
import {useTranslation} from 'react-i18next';

const DialogNumericInput = <T extends FieldValues>({
  controllerProps,
  id,
  label,
  leftElement,
}: {
  controllerProps: Omit<React.ComponentProps<typeof Controller<T>>, 'render'>;
  id: string;
  label: string;
  leftElement?: InputSharedProps['leftElement'];
}) => {
  const {t} = useTranslation();

  return (
    <Controller
      {...controllerProps}
      render={({
        field: {onChange, onBlur, ref, value}, fieldState: {error},
      }) => {
        const intent = error ? Intent.DANGER : Intent.NONE;

        if (typeof value !== 'number') {
          throw new TypeError('NumericInput value must be a number');
        }

        return (
          <FormGroup
            labelFor={id}
            labelInfo={controllerProps.rules?.required === undefined ? '' : t('common.required')}
            helperText={error?.message ?? ''}
            intent={intent}
            label={label}
          >
            <NumericInput
              large
              fill
              leftElement={leftElement}
              intent={intent}
              stepSize={1}
              value={value}
              inputRef={ref}
              min={typeof controllerProps.rules?.min === 'number' ? controllerProps.rules.min : 1}
              id={id}
              onValueChange={value => {
                onChange(value as unknown as PathValue<T, Path<T>>);
              }}
              onBlur={onBlur}
            />
          </FormGroup>
        );
      }}
    />
  );
};

export default DialogNumericInput;

