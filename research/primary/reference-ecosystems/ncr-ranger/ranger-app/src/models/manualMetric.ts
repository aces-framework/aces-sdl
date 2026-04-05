import {type ExerciseRole} from './scenario';

export type NewManualMetric = {
  exerciseId: string;
  deploymentId: string;
  entitySelector: string;
  name?: string;
  metricKey: string;
  role: ExerciseRole;
  textSubmission?: string;
};

export type ManualMetric = {
  id: string;
  exerciseId: string;
  deploymentId: string;
  userId: string;
  entitySelector: string;
  name?: string;
  sdlKey: string;
  description: string;
  role: ExerciseRole;
  textSubmission?: string;
  score?: number;
  maxScore: number;
  hasArtifact: boolean;
  createdAt: string;
  updatedAt: string;
};

export type UpdateManualMetric = {
  textSubmission?: string;
  score?: number;
};

export type FetchArtifact = {
  filename?: string;
  url?: string;
};
