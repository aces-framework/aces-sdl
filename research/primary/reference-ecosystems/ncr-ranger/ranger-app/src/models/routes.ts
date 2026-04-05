import {type ExerciseRole} from './scenario';

type ExerciseDetailRouteParameters = {
  exerciseId: string;
};

type DeploymentDetailRouteParameters = {
  exerciseId: string;
  deploymentId: string;
};

type DeploymentDetailScoresRouteParameters = {
  exerciseId: string;
  deploymentId: string;
  role: ExerciseRole;
};

type FormType =
  'training-objectives' | 'structure' | 'environment' | 'custom-elements' | 'plot' | 'final';

type OrderDetailRouteParamaters = {
  orderId: string;
  stage: FormType;
};

export type {
  ExerciseDetailRouteParameters,
  DeploymentDetailRouteParameters,
  DeploymentDetailScoresRouteParameters,
  OrderDetailRouteParamaters,
  FormType,
};
