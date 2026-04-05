import {FormGroup, Intent, TextArea} from '@blueprintjs/core';
import type React from 'react';
import {Controller, type FieldValues} from 'react-hook-form';
import {useTranslation} from 'react-i18next';

const DialogTextArea = <T extends FieldValues>({
  controllerProps,
  textAreaProps,
  id,
  label,
}: {
  controllerProps: Omit<React.ComponentProps<typeof Controller<T>>, 'render'>;
  textAreaProps?: Omit<React.ComponentProps<typeof TextArea>, 'ref' | 'value' | 'onChange'>;
  id: string;
  label: string;
}) => {
  const {t} = useTranslation();

  return (
    <Controller
      {...controllerProps}
      render={({
        field: {onChange, onBlur, ref, value}, fieldState: {error},
      }) => {
        const intent = error ? Intent.DANGER : Intent.NONE;
        if (typeof value !== 'string') {
          throw new TypeError('TextInput value must be a string');
        }

        return (
          <FormGroup
            labelFor={id}
            labelInfo={controllerProps.rules?.required === undefined ? '' : t('common.required')}
            helperText={error?.message ?? ''}
            intent={intent}
            label={label}
          >
            <TextArea
              {...(textAreaProps ?? {})}
              large
              intent={intent}
              value={value}
              inputRef={ref}
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

export default DialogTextArea;

