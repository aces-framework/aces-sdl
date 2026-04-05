
type ParticipantDeployment = {
  name: string;
  id: string;
  start: string;
  end: string;
  updatedAt: string;
};

type DeploymentForm = {
  name: string;
  deploymentGroup: string;
  groupNames: Array<{
    groupName: string;
  }>;
  count: number;
  start: string;
  end: string;
};

type NewDeployment = {
  name: string;
  deploymentGroup: string;
  groupName: string;
  sdlSchema: string;
  start: string;
  end: string;
};

type Deployment = {
  id: string;
  exerciseId: string;
  groupName?: string;
  createdAt: string;
  updatedAt: string;
} & NewDeployment;

type Deployers = Record<string, string[]>;
type DefaultDeployer = string;
export enum DeployerType {
  Switch = 'switch',
  Template = 'template',
  VirtualMachine = 'virtual_machine',
  Feature = 'feature',
  Condition = 'condition',
  Inject = 'inject',
}

export enum ElementStatus {
  Success = 'Success',
  Ongoing = 'Ongoing',
  Failed = 'Failed',
  Removed = 'Removed',
  RemoveFailed = 'RemoveFailed',
  ConditionSuccess = 'ConditionSuccess',
  ConditionPolling = 'ConditionPolling',
  ConditionClosed = 'ConditionClosed',
  ConditionWarning = 'ConditionWarning',
}

type DeploymentElement = {
  id: string;
  deploymentId: string;
  scenarioReference: string;
  handlerReference?: string;
  deployerType: DeployerType;
  status: ElementStatus;
  executorStdout?: string;
  executorStderr?: string;
  eventId?: string;
  parentNodeId?: string;
  errorMessage?: string;
};

export type {
  ParticipantDeployment,
  NewDeployment,
  Deployment,
  DeploymentElement,
  Deployers,
  DeploymentForm,
  DefaultDeployer,
};
