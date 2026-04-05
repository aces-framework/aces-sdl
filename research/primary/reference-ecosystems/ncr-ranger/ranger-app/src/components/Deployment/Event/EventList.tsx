import {Callout} from '@blueprintjs/core';
import React from 'react';
import {useTranslation} from 'react-i18next';
import {type DeploymentEvent} from 'src/models/exercise';
import {DateTime} from 'luxon';
import {type DeploymentElement} from 'src/models/deployment';
import PageHolder from 'src/components/PageHolder';
import {type Scenario} from 'src/models/scenario';
import {flattenEntities} from 'src/utils';
import {sortByProperty} from 'sort-by-property';
import EventCard from './EventCard';
import ParentlessEventCard from './ParentlessEventCard';

const ManagerEvents = ({scenario, deploymentEvents, deploymentElements}:
{
  scenario: Scenario | undefined;
  deploymentEvents: DeploymentEvent[] | undefined;
  deploymentElements: DeploymentElement[] | undefined;
}) => {
  const {t} = useTranslation();
  const scenarioEvents = scenario?.events;
  const scenarioNodes = scenario?.nodes;
  const flattenedEntities = scenario?.entities ? flattenEntities(scenario?.entities) : undefined;

  if (scenarioEvents && deploymentEvents && deploymentEvents.length > 0 && scenarioNodes) {
    return (
      <PageHolder>
        {
          deploymentEvents.slice().sort(sortByProperty('name', 'asc')).map(event => {
            const now = DateTime.utc();
            const start = DateTime.fromISO(event.start, {zone: 'UTC'});
            const end = DateTime.fromISO(event.end, {zone: 'UTC'});
            const eventConditionNames = scenarioEvents[event.name]?.conditions ?? [];
            const eventInjectNames = scenarioEvents[event.name]?.injects ?? [];

            if (eventConditionNames.length > 0 || eventInjectNames.length > 0) {
              return (
                <EventCard
                  key={event.name}
                  eventName={event.name}
                  event={event}
                  deploymentElements={deploymentElements}
                  eventConditionNames={eventConditionNames}
                  eventInjectNames={eventInjectNames}
                  scenarioNodes={scenarioNodes}
                  now={now}
                  start={start}
                  end={end}
                />
              );
            }

            return (
              <ParentlessEventCard
                key={event.name}
                eventName={event.name}
                event={event}
                entities={flattenedEntities}
              />
            );
          })
        }
      </PageHolder>
    );
  }

  const hasScenarioEvents = scenarioEvents && Object.keys(scenarioEvents).length > 0;
  const title = hasScenarioEvents ? t('deployments.events.noEventsYet')
    : t('deployments.events.noScenarioEvents');
  return (
    <Callout title={title}/>
  );
};

export default ManagerEvents;
