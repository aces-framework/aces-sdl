import {FormGroup, Intent, MenuItem} from '@blueprintjs/core';
import {Suggest} from '@blueprintjs/select';
import type React from 'react';
import {Controller, type FieldValues} from 'react-hook-form';
import {useTranslation} from 'react-i18next';

function onlyUnique(value: string, index: number, array: string[]) {
  return array.indexOf(value) === index;
}

const DialogSuggest = <T extends FieldValues>({
  controllerProps,
  id,
  label,
  items,
}: {
  controllerProps: Omit<React.ComponentProps<typeof Controller<T>>, 'render'>;
  id: string;
  label: string;
  items: string[];
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
          throw new TypeError('Suggest value must be a string');
        }

        return (
          <FormGroup
            labelFor={id}
            labelInfo={controllerProps.rules?.required === undefined ? '' : t('common.required')}
            helperText={error?.message ?? ''}
            intent={intent}
            label={label}
          >
            <Suggest
              ref={ref}
              inputValueRenderer={item => item}
              noResults={<MenuItem
                disabled
                text={t('common.noSuggestions')}/>}
              items={items.filter(onlyUnique)}
              itemRenderer={(item, {handleClick}) => (
                <MenuItem
                  key={item}
                  text={item}
                  onClick={handleClick}/>
              )}
              query={value ?? ''}
              onQueryChange={(newValue, event) => {
                if (newValue !== value && event) {
                  onChange(event);
                }
              }}
              onItemSelect={item => {
                if (typeof item === 'string') {
                  const event = {
                    target: {
                      value: item,
                      name: controllerProps.name,
                    },
                  } as unknown as React.ChangeEvent<HTMLInputElement>;
                  onChange(event);
                }
              }}
            />
          </FormGroup>
        );
      }}
    />
  );
};

export default DialogSuggest;

