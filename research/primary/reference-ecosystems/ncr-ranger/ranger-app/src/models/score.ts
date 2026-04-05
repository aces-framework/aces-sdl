export type Score = {
  id: string;
  exerciseId: string;
  deploymentId: string;
  metricName?: string;
  metricKey: string;
  value: number;
  timestamp: string;
  vmName: string;
};

export type RoleScore = {
  role: string;
  score: number;
};

export type DeploymentScore = {
  deploymentId: string;
  roleScores: RoleScore[];
};
