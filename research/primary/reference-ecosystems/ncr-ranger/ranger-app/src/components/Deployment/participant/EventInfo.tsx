import React from 'react';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import {useTranslation} from 'react-i18next';
import {useSelector} from 'react-redux';
import {useParams} from 'react-router-dom';
import {type DeploymentEvent} from 'src/models/exercise';
import {type DeploymentDetailRouteParameters} from 'src/models/routes';
import {useParticipantGetEventInfoQuery} from 'src/slices/apiSlice';
import {selectedEntity} from 'src/slices/userSlice';
import ContentIFrame from 'src/components/ContentIFrame';
import {Divider} from '@blueprintjs/core';
import {formatStringToDateTime} from 'src/utils';

const EventInfo = ({eventName, event}:
{eventName: string | undefined; event: DeploymentEvent ;
}) => {
  const {t} = useTranslation();
  const {exerciseId, deploymentId} = useParams<DeploymentDetailRouteParameters>();
  const entitySelector = useSelector(selectedEntity);
  const eventInfoDataChecksum = event?.eventInfoDataChecksum;
  const {data: eventInfo} = useParticipantGetEventInfoQuery(
    exerciseId && deploymentId && entitySelector && eventInfoDataChecksum
      ? {exerciseId, deploymentId, entitySelector, eventInfoDataChecksum} : skipToken);

  if (!eventInfo?.checksum) {
    return (
      <div key={event.id} className='p-2'>
        <details className='p-2 border-2 border-slate-300 shadow-md '>
          <summary className='font-bold text-xl'>
            {eventName ?? event.name}
          </summary>
          <div className='mt-4 ml-2 text-sm'>
            {event.description ?? t('participant.exercise.events.noDescription')}
            <Divider className='mt-4'/>
            <div className='pt-2 text-slate-600 italic'>
              {t('participant.exercise.events.triggeredAt',
                {date: formatStringToDateTime(event.triggeredAt)})}
            </div>
          </div>
        </details>
      </div>
    );
  }

  return (
    <div key={event.id} className='p-2'>
      <details className='p-2 border-2 border-slate-300 shadow-md '>
        <summary className='font-bold text-xl'>
          {eventName ?? event.name}
        </summary>
        <div className='mt-4 text-sm'>
          <div className='m-4'>
            {event.description ?? ''}
          </div>
          <div>
            <ContentIFrame content={eventInfo?.content}/>
          </div>
          <Divider/>
          <div className='ml-2 pt-2 text-slate-600 italic'>
            {t('participant.exercise.events.triggeredAt',
              {date: formatStringToDateTime(event.triggeredAt)})}
          </div>
        </div>
      </details>
    </div>
  );
};

export default EventInfo;
