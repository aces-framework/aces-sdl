import type React from 'react';
import {useEffect, type ChangeEvent} from 'react';
import {useTranslation} from 'react-i18next';
import {type Participant} from 'src/models/participant';

type EntitySelectProps = {
  participants: Participant[];
  selectedEntityKey?: string;
  onChange: (selectedKey: string | undefined) => void;
};

const EntitySelect: React.FC<EntitySelectProps> = ({
  participants = [],
  selectedEntityKey,
  onChange,
}) => {
  const {t} = useTranslation();

  useEffect(() => {
    if (participants.length === 1 && !selectedEntityKey) {
      onChange(participants[0].selector);
    }
  }, [participants, selectedEntityKey, onChange]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selectedKey = event.target.value || undefined;
    onChange(selectedKey);
  };

  return (
    <div className='
    bp5-html-select
    bp5-minimal
    bp5-large'
    >
      <select
        value={selectedEntityKey ?? ''}
        onChange={handleChange}
      >
        <option value=''>{t('deployments.entitySelect')}</option>
        {participants.map(participant => (
          <option key={participant.id} value={participant.selector}>
            {participant.selector}
          </option>
        ))}
      </select>
      <span className='bp5-icon bp5-icon-double-caret-vertical'/>
    </div>
  );
};

export default EntitySelect;
