import type React from 'react';
import {HTMLSelect} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';

const SortOrderSelect = ({sortOrder, handleSortOrderChange}:
{sortOrder: string;
  handleSortOrderChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
}) => {
  const {t} = useTranslation();

  return (
    <HTMLSelect
      value={sortOrder}
      onChange={handleSortOrderChange}
    >
      <option value=''>{t('scoreTable.orderPlaceholder')}</option>
      <option value='scoreDesc'>{t('scoreTable.scoreDescending')}</option>
      <option value='scoreAsc'>{t('scoreTable.scoreAscending')}</option>
      <option value='nameDesc'>{t('scoreTable.nameDescending')}</option>
      <option value='nameAsc'>{t('scoreTable.nameAscending')}</option>
      <option value='createdDesc'>{t('scoreTable.createdAtDescending')}</option>
      <option value='createdAsc'>{t('scoreTable.createdAtAscending')}</option>
    </HTMLSelect>
  );
};

export default SortOrderSelect;
