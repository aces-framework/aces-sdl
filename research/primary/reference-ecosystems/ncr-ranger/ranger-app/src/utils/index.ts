import {Colors, type TreeNodeInfo} from '@blueprintjs/core';
import {
  DeployerType,
  ElementStatus,
  type DeploymentElement,
} from 'src/models/deployment';
import {type AdUser} from 'src/models/groups';
import {type Participant} from 'src/models/participant';
import {
  type Entity,
  ExerciseRole,
  type Metric,
  type Scenario,
  type TloMapsByRole,
  type TrainingLearningObjective,
  type ScoringMetadata,
  type Evaluation,
} from 'src/models/scenario';
import {type Score} from 'src/models/score';
import {
  deleteEntityConnectionButton,
} from 'src/components/Deployment/EntityTree';
import {type TFunction} from 'i18next';
import {DateTime} from 'luxon';
import {type FormType} from 'src/models/routes';

export const createEntityTree = (
  clickedDelete: (participantId: string) => void,
  entities: Record<string, Entity>,
  participants: Participant[] = [],
  users: AdUser[] = [],
  selector?: string,
  // eslint-disable-next-line max-params
): TreeNodeInfo[] => {
  const sortedEntityKeys = Object.keys(entities).sort((a, b) => {
    const entityA = entities[a];
    const entityB = entities[b];
    return (entityA.name ?? a).localeCompare(entityB.name ?? b);
  });

  const tree: TreeNodeInfo[] = [];
  for (const entityId of sortedEntityKeys) {
    const entity = entities[entityId];
    const id = selector ? `${selector}.${entityId}` : entityId;
    const matchingParticipant = participants.find(participant => participant.selector === id);
    const matchingUser = users.find(user => user.id === matchingParticipant?.userId);
    const entityNode: TreeNodeInfo = {
      id,
      label: `${entity.name ?? entityId}${matchingUser ? ': ' : ''}${matchingUser?.username ?? ''}`,
      icon: 'person',
      isExpanded: true,
      secondaryLabel: deleteEntityConnectionButton(
        clickedDelete,
        matchingParticipant?.id,
      ),
    };
    if (entity.entities) {
      entityNode.childNodes = createEntityTree(
        clickedDelete,
        entity.entities,
        participants,
        users,
        id,
      );
    }

    tree.push(entityNode);
  }

  return tree;
};

export const getWebsocketBase = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  return `${protocol}://${host}`;
};

export const isDevelopment = () =>
  import.meta.env.DEV;

export function groupByMetricNameAndVmName(array: Score[]) {
  return array.reduce<Record<string, Score[]>>(
    (groupedMap, element) => {
      const metricReference = element.metricName ?? element.metricKey;
      const key = metricReference.concat(' - ', element.vmName);
      if (groupedMap[key]) {
        groupedMap[key].push(element);
      } else {
        groupedMap[key] = [element];
      }

      return groupedMap;
    }, {});
}

export const groupBy = <T, K extends keyof any>(array: T[], key: (i: T) => K) =>
  array.reduce<Record<K, T[]>>((groups, item) => {
    (groups[key(item)] ||= []).push(item);
    return groups;
  // eslint-disable-next-line @typescript-eslint/prefer-reduce-type-parameter
  }, {} as Record<K, T[]>);

export const defaultColors = [
  '#147EB3',
  '#29A634',
  '#D1980B',
  '#D33D17',
  '#9D3F9D',
  '#00A396',
  '#DB2C6F',
  '#8EB125',
  '#946638',
  '#7961DB',
];

export const getRoleColor = (role: ExerciseRole) => {
  switch (role) {
    case (ExerciseRole.Red): {
      return Colors.RED2;
    }

    case (ExerciseRole.Green): {
      return Colors.GREEN3;
    }

    case (ExerciseRole.Blue): {
      return Colors.BLUE2;
    }

    case (ExerciseRole.White): {
      return Colors.GRAY4;
    }

    default: {
      return Colors.GRAY1;
    }
  }
};

export const roundToDecimalPlaces
= (value: number, decimalPlaces = 2): number => {
  const scale = 10 ** decimalPlaces;
  return Math.round(value * scale) / scale;
};

export type RequireAtLeastOne<T, Keys extends keyof T = keyof T> =
    Pick<T, Exclude<keyof T, Keys>>
    & {
      [K in Keys]-?: Required<Pick<T, K>> & Partial<Pick<T, Exclude<Keys, K>>>
    }[Keys];

export function isNonNullable<T>(value: T): value is NonNullable<T> {
  return value !== null && value !== undefined;
}

export const findLatestScore = (scores: Score[]) => {
  if (scores.length > 0) {
    const latestScore = scores.reduce((previous, current) =>
      (Date.parse(previous?.timestamp)
      > Date.parse(current?.timestamp)) ? previous : current);
    return latestScore;
  }

  return undefined;
};

export const findLatestScoresByVms = (scores: Score[]) => {
  const uniqueVmNames = [...new Set(scores
    .map(score => score.vmName))];
  const latestScoresByVm = uniqueVmNames
    .reduce<Score[]>((latestVms, vmName) => {
    const scoresByVm = scores.filter(score =>
      score.vmName === vmName);
    const latestScoreValue = findLatestScore(scoresByVm);
    if (latestScoreValue) {
      latestVms.push(latestScoreValue);
      return latestVms;
    }

    return [];
  }, []);

  return latestScoresByVm;
};

export function sumScoresByMetrics(
  metricKeys: string[], scoresByMetric: Record<string, Score[]>): number {
  return metricKeys.reduce(
    (metricScoreSum, metricKey) => {
      if (scoresByMetric[metricKey]) {
        const currentScore = findLatestScore(scoresByMetric[metricKey]);
        if (currentScore?.value) {
          metricScoreSum += Number(currentScore?.value);
        }
      }

      return metricScoreSum;
    }, 0);
}

export function sumScoresByRole(uniqueVmNames: string[], roleScores: Score[]) {
  return uniqueVmNames.reduce((totalScoreSum, vmName) => {
    const vmScores = roleScores.filter(score => score.vmName === vmName);

    const scoresByMetric = groupBy(vmScores, score => score.metricName ?? score.metricKey);
    const metricNames = Object.keys(scoresByMetric);
    const metricScoreSum = sumScoresByMetrics(metricNames, scoresByMetric);
    totalScoreSum += metricScoreSum;
    return totalScoreSum;
  }, 0);
}

export function getTloKeysByRole(
  entities: Record<string, Entity>,
  role: ExerciseRole) {
  const entityValues = Object.values(entities);
  const roleEntities = entityValues.slice().filter(entity =>
    entity.role?.valueOf() === role,
  );
  const tloKeys = roleEntities.slice().reduce<string []>(
    (tloKeys, entity) => {
      if (entity.tlos) {
        tloKeys = tloKeys.concat(entity?.tlos);
      }

      return tloKeys;
    }, []);
  return tloKeys;
}

export function groupTloMapsByRoles(
  entities: Record<string, Entity>,
  tlos: Record<string, TrainingLearningObjective>,
  roles: ExerciseRole[],
) {
  const tloMapsByRole = roles.reduce<TloMapsByRole>((tloMapsByRole, role) => {
    const roleTloNames = getTloKeysByRole(entities, role);
    const roleTloMap
      = roleTloNames.reduce<Record<string, TrainingLearningObjective>>(
        (roleTloMap, tloName) => {
          if (tlos[tloName]) {
            roleTloMap[tloName] = tlos[tloName];
          }

          return roleTloMap;
        }, {});

    tloMapsByRole[role] = roleTloMap;
    return tloMapsByRole;
  }, {});
  return tloMapsByRole;
}

export function flattenEntities(entities: Record<string, Entity>) {
  const outputEntities: Record<string, Entity> = {};

  for (const key of Object.keys(entities)) {
    const childEntity = entities[key];
    outputEntities[key] = childEntity;

    if (childEntity.entities) {
      const nested = flattenEntities(childEntity.entities);
      for (const nestedKey of Object.keys(nested)) {
        outputEntities[`${key}.${nestedKey}`] = nested[nestedKey];
      }
    }
  }

  return outputEntities;
}

export function getUniqueRoles(entities: Record<string, Entity>) {
  const rolesSet = Object.values(entities)
    .reduce<Set<ExerciseRole>>((accumulator, entity) => {
    if (entity?.role) {
      accumulator.add(entity.role);
    }

    return accumulator;
  }, new Set<ExerciseRole>());

  return Array.from(rolesSet);
}

export const getTloKeysForEntityOrClosestParent
= (currentEntityKey: string, flattenedEntities: Record<string, Entity>): string[] => {
  let currentEntity = flattenedEntities[currentEntityKey];

  while (currentEntity && !currentEntity.tlos && currentEntityKey.includes('.')) {
    const lastPeriodIndex = currentEntityKey.lastIndexOf('.');
    currentEntityKey = currentEntityKey.slice(0, Math.max(0, lastPeriodIndex));
    currentEntity = flattenedEntities[currentEntityKey];
  }

  return currentEntity?.tlos ?? [];
};

export const getMetricsByEntityKey
= (entityKey: string, scenario: Scenario): Record<string, Metric> => {
  const entities = scenario?.entities;
  const tlos = scenario?.tlos;
  const evaluations = scenario?.evaluations;
  const metrics = scenario?.metrics;

  if (entities && tlos && evaluations && metrics) {
    const flattenedEntities = flattenEntities(entities);
    const entity = flattenedEntities[entityKey];

    if (entity) {
      const entityTloKeys = getTloKeysForEntityOrClosestParent(entityKey, flattenedEntities);
      const entityMetricKeys = entityTloKeys.map(tloKey => tlos[tloKey])
        .map(tlo => tlo.evaluation)
        .map(evaluationKey => evaluations[evaluationKey])
        .flatMap(evaluation => evaluation.metrics);

      const entityMetrics = entityMetricKeys
        .reduce<Record<string, Metric>>((accumulator, metricKey) => {
        if (metrics[metricKey]) {
          accumulator[metricKey] = metrics[metricKey];
        }

        return accumulator;
      }, {});

      return entityMetrics;
    }
  }

  return {};
};

export const calculateTotalScoreForRole = ({scenario, scores, role}: {
  scenario: Scenario;
  scores: Score[];
  role: ExerciseRole;
}) => {
  const {entities = {}, tlos = {}, evaluations = {}, metrics = {}} = scenario ?? {};
  const flattenedEntities = flattenEntities(entities);
  const roleTloNames = getTloKeysByRole(flattenedEntities, role);
  const roleEvaluationNames = roleTloNames.flatMap(tloName =>
    tlos[tloName]?.evaluation ?? []);
  const roleMetricKeys = Array.from(new Set(roleEvaluationNames
    .flatMap(evaluationName =>
      evaluations[evaluationName]?.metrics ?? [])));
  const roleMetrics = new Set(roleMetricKeys
    .map(metricKey => metrics[metricKey]?.name ?? metricKey)
    .filter(Boolean));

  const roleScores = scores.filter(score =>
    roleMetrics.has(score.metricName ?? score.metricKey));

  const uniqueVmNames = [...new Set(roleScores.map(score => score.vmName))];
  const totalRoleScore = sumScoresByRole(uniqueVmNames, roleScores);
  return totalRoleScore;
};

export const getMetricReferencesByRole = (
  scoringData: ScoringMetadata,
) => {
  const flattenedEntities = flattenEntities(scoringData.entities);
  const result = Object.values(flattenedEntities)
    .reduce<Record<ExerciseRole, Set<string>>>((accumulator, entity) => {
    const role = entity.role;
    const entityTlos = entity.tlos;
    if (role && entityTlos) {
      const metricReferences = entityTlos.map(tloKey => scoringData.tlos[tloKey])
        .map(tlo => tlo.evaluation)
        .map(evaluationKey => scoringData.evaluations[evaluationKey])
        .flatMap(evaluation => evaluation.metrics)
        .map(metricKey => scoringData.metrics[metricKey].name ?? metricKey);

      for (const metricReference of metricReferences) {
        accumulator[role].add(metricReference);
      }
    }

    return accumulator;
  }, {
    [ExerciseRole.Blue]: new Set(),
    [ExerciseRole.Green]: new Set(),
    [ExerciseRole.Red]: new Set(),
    [ExerciseRole.White]: new Set(),
  });

  return result;
};

export const tableHeaderBgColor = {
  [ExerciseRole.Blue]: 'bg-blue-300',
  [ExerciseRole.Green]: 'bg-green-300',
  [ExerciseRole.Red]: 'bg-red-300',
  [ExerciseRole.White]: 'bg-gray-300',
};

export const tableRowBgColor = {
  [ExerciseRole.Blue]: 'bg-blue-50',
  [ExerciseRole.Green]: 'bg-green-50',
  [ExerciseRole.Red]: 'bg-red-50',
  [ExerciseRole.White]: 'bg-gray-50',
};

export function tryIntoScoringMetadata(scenario?: Scenario): ScoringMetadata | undefined {
  if (scenario?.entities && scenario?.tlos && scenario?.evaluations && scenario?.metrics) {
    return {
      startTime: scenario.start,
      endTime: scenario.end,
      entities: scenario.entities,
      tlos: scenario.tlos,
      evaluations: scenario.evaluations,
      metrics: scenario.metrics,
    };
  }
}

export const getElementNameById
= (deploymentElements: DeploymentElement[], id: string): string | undefined => {
  if (deploymentElements) {
    const vm = deploymentElements.find(element => element.handlerReference === id);
    return vm?.scenarioReference ?? undefined;
  }
};

export const sumMetricMaxScores = (metricKeys: string[], metrics: Record<string, Metric>) =>
  metricKeys.reduce((sum, metricKey) => sum + metrics[metricKey].max_score, 0);

export const getEvaluationMinScore = (evaluation: Evaluation, summedMaxScore: number) => {
  if (evaluation.min_score?.percentage) {
    return roundToDecimalPlaces(evaluation.min_score.percentage / 100 * summedMaxScore);
  }

  if (evaluation.min_score?.absolute) {
    return evaluation.min_score?.absolute;
  }

  return 0;
};

export const isVMDeploymentOngoing = (deploymentElements: DeploymentElement[]) => (
  deploymentElements.some(
    element => element.deployerType === DeployerType.VirtualMachine
    && element.status === ElementStatus.Ongoing)
);

export const getReadableElementStatus = (t: TFunction, status: ElementStatus): string => {
  switch (status) {
    case ElementStatus.Success: {
      return t('deployments.status.success');
    }

    case ElementStatus.Ongoing: {
      return t('deployments.status.ongoing');
    }

    case ElementStatus.Failed: {
      return t('deployments.status.failed');
    }

    case ElementStatus.Removed: {
      return t('deployments.status.removed');
    }

    case ElementStatus.RemoveFailed: {
      return t('deployments.status.removeFailed');
    }

    case ElementStatus.ConditionSuccess: {
      return t('deployments.status.conditionSuccess');
    }

    case ElementStatus.ConditionPolling: {
      return t('deployments.status.conditionPolling');
    }

    case ElementStatus.ConditionClosed: {
      return t('deployments.status.conditionClosed');
    }

    case ElementStatus.ConditionWarning: {
      return t('deployments.status.conditionWarning');
    }

    default: {
      return t('deployments.status.unknown');
    }
  }
};

export const getReadableDeployerType = (t: TFunction, type: DeployerType): string => {
  switch (type) {
    case DeployerType.Switch: {
      return t('deployments.deployerTypes.switch');
    }

    case DeployerType.Template: {
      return t('deployments.deployerTypes.template');
    }

    case DeployerType.VirtualMachine: {
      return t('deployments.deployerTypes.virtualMachine');
    }

    case DeployerType.Feature: {
      return t('deployments.deployerTypes.feature');
    }

    case DeployerType.Condition: {
      return t('deployments.deployerTypes.condition');
    }

    case DeployerType.Inject: {
      return t('deployments.deployerTypes.inject');
    }

    default: {
      return t('deployments.deployerTypes.unknown');
    }
  }
};

export const formatStringToDateTime = (date: string) => DateTime.fromISO(date, {zone: 'utc'})
  .setZone('local')
  .toLocaleString(DateTime.DATETIME_SHORT_WITH_SECONDS);

export const getBreadcrumIntent = (formType: FormType, currentFormType: FormType) => {
  if (formType === currentFormType) {
    return 'primary';
  }

  if (formType === 'training-objectives' && currentFormType !== 'training-objectives') {
    return 'success';
  }

  if (formType === 'structure'
    && currentFormType !== 'training-objectives'
    && currentFormType !== 'structure') {
    return 'success';
  }

  if (formType === 'environment'
  && currentFormType !== 'training-objectives'
  && currentFormType !== 'structure'
  && currentFormType !== 'environment') {
    return 'success';
  }

  if (formType === 'custom-elements'
  && currentFormType !== 'training-objectives'
  && currentFormType !== 'structure'
  && currentFormType !== 'environment'
  && currentFormType !== 'custom-elements') {
    return 'success';
  }

  if (currentFormType === 'final') {
    return 'success';
  }

  return 'none';
};

export const dowloadFile = async (
  fileLink: string, token: string, fileName: string, onError: () => void) => {
  try {
    const response = await fetch(fileLink ?? '', {
      headers: {
        Authorization: token ? `Bearer ${token}` : '',
      },
    });
    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.append(a);
      a.click();
      a.remove();
    } else {
      onError();
    }
  } catch {
    onError();
  }
};
