// EventCard.tsx
import type React from 'react';
import {H3} from '@blueprintjs/core';
import {formatStringToDateTime} from 'src/utils';
import {useTranslation} from 'react-i18next';
import {type DeploymentEvent} from 'src/models/exercise';
import {type Entity} from 'src/models/scenario';
import EventInfo from './EventInfo';
import ProgressBarWithTimer from './EventProgressBar';

type ParentlessEventCardProps = {
  eventName: string;
  event: DeploymentEvent;
  entities: Record<string, Entity> | undefined;
};

const ParentlessEventCard: React.FC<ParentlessEventCardProps>
= ({eventName, event, entities}) => {
  const {t} = useTranslation();
  const entityKeysWithEventName = Object.keys(entities ?? {})
    .filter(key => entities?.[key].events?.includes(eventName))
    .sort();

  return (
    <div key={eventName} className='border-2 rounded-lg p-4 mb-4 '>
      <div className='flex justify-between mb-4'>
        <H3 className='text-2xl font-bold'>{eventName}</H3>
        <span className='text-xs text-gray-500 italic'>
          {t('deployments.events.infoOnly')}
        </span>
      </div>
      <ProgressBarWithTimer
        allNodesHaveTriggered={event.hasTriggered}
        event={event}/>
      <div className='mb-6 text-base'>
        <div className='mb-6'>
          <p>
            <span className='font-medium'>{t('deployments.startTime')}: </span>
            {formatStringToDateTime(event.start)}
          </p>
          <p>
            <span className='font-medium'>{t('deployments.endTime')}: </span>
            {formatStringToDateTime(event.end)}
          </p>
          <p>
            <span className='font-medium'>{t('deployments.events.description')} </span>
            {event.description ?? t('deployments.events.noDescription')}
          </p>
        </div>
        <EventInfo eventName={eventName} event={event}/>
      </div>
      {entityKeysWithEventName.length > 0 && (
        <div className='flex flex-col'>
          <h4 className='text-xl font-semibold mb-2'>{t('deployments.events.informedEntities')}</h4>
          <ul className='list-disc list-inside'>
            {entityKeysWithEventName.map(entityKey => (
              <li key={entityKey}>{entities?.[entityKey].name ?? entityKey}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ParentlessEventCard;
