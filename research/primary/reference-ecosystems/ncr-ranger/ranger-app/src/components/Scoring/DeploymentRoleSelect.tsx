import type React from 'react';
import {HTMLSelect} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import {ExerciseRole} from 'src/models/scenario';

const DeploymentRoleSelect = ({selectedRole, handleRoleChange}:
{selectedRole: string;
  handleRoleChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
}) => {
  const {t} = useTranslation();
  const roles = Object.values(ExerciseRole);

  return (
    <HTMLSelect
      value={selectedRole}
      onChange={handleRoleChange}
    >
      <option value=''>{t('scoreTable.rolePlaceholder')}</option>
      <option value='all'>{t('scoreTable.allRoles')}</option>
      {roles.map((role: ExerciseRole) => (
        <option key={role} value={role}>{role}</option>
      ))}
    </HTMLSelect>
  );
};

export default DeploymentRoleSelect;
