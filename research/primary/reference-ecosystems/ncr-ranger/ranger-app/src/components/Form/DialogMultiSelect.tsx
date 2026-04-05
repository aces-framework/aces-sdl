import {FormGroup, MenuItem} from '@blueprintjs/core';
import {MultiSelect} from '@blueprintjs/select';
import type React from 'react';
import {
  useFieldArray,
  type FieldValues,
  type ArrayPath,
  type Control,
  type FieldArray,
} from 'react-hook-form';

const DialogMultiSelect = <T extends FieldValues, B extends ArrayPath<T>, C extends string>({
  control,
  id,
  label,
  textRenderer,
  name,
  keyName,
  items,
}: {
  control: Control<T>;
  name: B;
  id: string;
  label: string;
  keyName: C;
  items: Array<FieldArray<T, B> & {[K in C]?: string}>;
  textRenderer: (item: FieldArray<T, B>) => string;
}) => {
  const {
    fields,
    append,
    remove,
  } = useFieldArray({
    control,
    name,
  });

  return (
    <FormGroup
      labelFor={id}
      label={label}
    >
      <MultiSelect<FieldArray<T, B> & {[K in C]?: string}>
        itemRenderer={item => {
          const selected = fields
            .some(field => field[keyName as unknown as keyof FieldArray<T, B>]
                === item[keyName as unknown as keyof FieldArray<T, B>]);
          return (
            (
              <MenuItem
                key={item[keyName] ?? Math.random().toString(36).slice(7)}
                roleStructure='listoption'
                selected={selected}
                disabled={selected}
                shouldDismissPopover={false}
                text={textRenderer(item)}
                onClick={() => {
                  append(item);
                }}
              />
            )
          );
        }}
        items={items}
        selectedItems={fields}
        tagRenderer={textRenderer}
        onItemSelect={item => {
          append(item);
        }}
        onRemove={(_item, index) => {
          remove(index);
        }}
      />
    </FormGroup>
  );
};

export default DialogMultiSelect;

