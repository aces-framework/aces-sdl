import {Callout} from '@blueprintjs/core';
import React from 'react';
import {useTranslation} from 'react-i18next';
import {type DeploymentEvent} from 'src/models/exercise';
import {type Event} from 'src/models/scenario';
import EventInfo from './EventInfo';

const Events = ({scenarioEvents, deploymentEvents}:
{scenarioEvents: Record<string, Event> | undefined; deploymentEvents: DeploymentEvent[] | undefined;
}) => {
  const {t} = useTranslation();

  if (scenarioEvents && deploymentEvents && deploymentEvents.length > 0) {
    return (
      <>
        {
          deploymentEvents.map(event => (
            <EventInfo
              key={event.id}
              eventName={scenarioEvents[event.name]?.name ?? event.name}
              event={event}/>
          ))
        }
      </>
    );
  }

  if (deploymentEvents && deploymentEvents.length === 0) {
    return (
      <Callout title={t('participant.exercise.events.noTriggeredEvents') ?? ''}/>
    );
  }

  return (
    <Callout title={t('participant.exercise.events.noEvents') ?? ''}/>
  );
};

export default Events;
