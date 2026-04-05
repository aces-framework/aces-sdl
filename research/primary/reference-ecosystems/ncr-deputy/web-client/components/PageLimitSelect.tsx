import { HTMLSelect } from '@blueprintjs/core';
import { ChangeEvent } from 'react';
import { LIMIT_OPTIONS } from '../constants/constants';

const PageLimitSelect = ({
  selectedLimit,
  onChange,
}: {
  selectedLimit: number;
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
}) => {
  return (
    <HTMLSelect
      id="limit"
      iconName="caret-down"
      value={selectedLimit}
      onChange={onChange}
    >
      {LIMIT_OPTIONS.map((limit) => (
        <option key={limit} value={limit}>
          {limit}
        </option>
      ))}
    </HTMLSelect>
  );
};

export default PageLimitSelect;
