import {type Scenario, type Source} from 'src/models/scenario';

export const getPackageSources = (scenario: Scenario): Source[] => {
  const sources: Source[] = [];
  if (scenario?.nodes) {
    for (const nodeName of Object.keys(scenario.nodes)) {
      const node = scenario.nodes[nodeName];
      if (node.source) {
        sources.push(node.source);
      }
    }
  }

  if (scenario?.features) {
    for (const featureName of Object.keys(scenario.features)) {
      const feature = scenario.features[featureName];
      if (feature.source) {
        sources.push(feature.source);
      }
    }
  }

  if (scenario?.conditions) {
    for (const conditionName of Object.keys(scenario.conditions)) {
      const condition = scenario.conditions[conditionName];
      if (condition.source) {
        sources.push(condition.source);
      }
    }
  }

  if (scenario?.injects) {
    for (const injectName of Object.keys(scenario.injects)) {
      const inject = scenario.injects[injectName];
      if (inject.source) {
        sources.push(inject.source);
      }
    }
  }

  if (scenario?.events) {
    for (const eventName of Object.keys(scenario.events)) {
      const event = scenario.events[eventName];
      if (event.source) {
        sources.push(event.source);
      }
    }
  }

  return sources;
};
