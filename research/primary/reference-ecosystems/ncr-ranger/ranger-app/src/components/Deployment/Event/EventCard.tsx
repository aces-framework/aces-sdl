import type React from 'react';
import {H3, H4, Icon} from '@blueprintjs/core';
import {sortByProperty} from 'sort-by-property';
import {formatStringToDateTime} from 'src/utils';
import {useTranslation} from 'react-i18next';
import {ElementStatus, type DeploymentElement} from 'src/models/deployment';
import {type DeploymentEvent} from 'src/models/exercise';
import {type DateTime} from 'luxon';
import {type Node} from 'src/models/scenario';
import EventInfo from './EventInfo';
import ProgressBarWithTimer from './EventProgressBar';

type EventCardProps = {
  eventName: string;
  event: DeploymentEvent;
  deploymentElements: DeploymentElement[] | undefined;
  eventConditionNames: string[] | undefined;
  eventInjectNames: string[] | undefined;
  scenarioNodes: Record<string, Node>;
  now: DateTime;
  start: DateTime;
  end: DateTime;
};

const EventCard: React.FC<EventCardProps>
= ({eventName, event, deploymentElements, eventConditionNames, eventInjectNames, scenarioNodes,
  now, start, end}) => {
  const {t} = useTranslation();
  const allNodesHaveTriggered = event.hasTriggered;
  const conditionElements = deploymentElements?.filter(element =>
    eventConditionNames?.includes(element.scenarioReference),
  );
  const eventHasSdlInjects = eventInjectNames && eventInjectNames.length > 0;
  const injectElements = deploymentElements?.filter(element =>
    eventInjectNames?.includes(element.scenarioReference),
  );
  const eventHasInjectDeploymentElements = injectElements && injectElements.length > 0;
  const nodesByEventInjects: Record<string, string[]> = Object.entries(scenarioNodes)
    .reduce<Record<string, string[]>>((acc, [nodeKey, node]) => {
    const nodeInjects = Object.keys(node.injects ?? {});
    for (const injectName of nodeInjects) {
      if (eventInjectNames?.includes(injectName)) {
        if (!acc[injectName]) {
          acc[injectName] = [];
        }

        acc[injectName].push(nodeKey);
      }
    }

    return acc;
  }, {});

  return (
    <div key={eventName} className='border-2 rounded-lg p-4 mb-4 '>
      <H3 className='text-2xl font-bold mb-4'>{eventName}</H3>
      <ProgressBarWithTimer
        allNodesHaveTriggered={allNodesHaveTriggered}
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
            <span className='font-medium'>{t('deployments.events.triggeredAt')} </span>
            {event.hasTriggered ? formatStringToDateTime(event.triggeredAt)
              : t('deployments.events.notTriggered')}
          </p>
          <p>
            <span className='font-medium'>{t('deployments.events.description')} </span>
            {event.description ?? t('deployments.events.noDescription')}
          </p>
        </div>
        <EventInfo eventName={eventName} event={event}/>
      </div>

      {conditionElements && conditionElements.length > 0 && (
        <>
          <H4 className='mt-6 text-xl font-semibold'>
            {t('deployments.events.conditions')}
          </H4>
          {conditionElements.sort(sortByProperty('scenarioReference', 'desc'))
            .map(conditionElement => (
              <div
                key={conditionElement.id}
                className='flex items-center border-2 rounded-lg p-2 mb-4'
              >

                {conditionElement.status === ElementStatus.ConditionSuccess
                        && <Icon icon='tick' size={30} color='green'/>}

                {now > end && conditionElement.status !== ElementStatus.ConditionSuccess
                        && <Icon icon='cross' size={30} color='red'/>}

                {now > start && now < end
                && (conditionElement.status === ElementStatus.ConditionPolling
                || conditionElement.status === ElementStatus.Ongoing)
                         && <Icon
                           icon='refresh'
                           size={15}
                           color='orange'
                           className='animate-spin'/>}

                <div className='font-bold mx-2 text-lg'>
                  {deploymentElements?.find(element =>
                    element.handlerReference === conditionElement.parentNodeId)?.scenarioReference}
                  <span className='pl-2'>- {conditionElement.scenarioReference}</span>
                </div>
              </div>
            ))}
        </>
      )}

      {eventHasSdlInjects && !eventHasInjectDeploymentElements && (
        <>
          <H4
            className='mt-6 text-xl font-semibold'
          >
            {t('deployments.events.injects')}
          </H4>
          {eventInjectNames.map(injectName => (
            nodesByEventInjects[injectName].map(nodeName => (
              <div
                key={nodeName}
                className='flex items-center border-2 rounded-lg p-2 mb-4'
              >
                <Icon icon='time' size={30} color='gray'/>
                <div className='font-bold mx-2 text-lg'>
                  <div>{nodeName} - {injectName}</div>
                </div>
              </div>
            ))
          ))}
        </>
      )}

      {(eventHasInjectDeploymentElements && (
        <>
          <H4 className='mt-6 text-xl font-semibold'>
            {t('deployments.events.injects')}
          </H4>
          {injectElements.sort(sortByProperty('scenarioReference', 'desc'))
            .map(injectElement => (
              <div
                key={injectElement.id}
                className='flex items-center border-2 rounded-lg p-2 mb-4'
              >
                {injectElement.status === ElementStatus.Success
              && <Icon icon='tick' size={30} color='green'/>}

                {injectElement.status === ElementStatus.Failed
              && <Icon icon='cross' size={30} color='red'/>}

                {injectElement.status === ElementStatus.Ongoing
              && <Icon icon='refresh' size={30} color='orange' className='animate-spin'/>}

                <div className='font-bold mx-2 text-lg'>
                  {deploymentElements?.find(element =>
                    element.handlerReference === injectElement.parentNodeId)?.scenarioReference}
                  <span className='pl-2'>- {injectElement.scenarioReference}</span>
                </div>
              </div>
            ))}
        </>
      )
      )}

    </div>
  );
};

export default EventCard;
