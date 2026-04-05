
export type Condition = {
  name?: string;
  description?: string;
  command?: string;
  interval?: number;
  source?: Source;
};

export enum ExerciseRole {
  Blue = 'Blue',
  Green = 'Green',
  Red = 'Red',
  White = 'White',
}

export const ExerciseRoleOrder = {
  [ExerciseRole.Blue]: 1,
  [ExerciseRole.Green]: 2,
  [ExerciseRole.Red]: 3,
  [ExerciseRole.White]: 4,
};

export type Entity = {
  name?: string;
  description?: string;
  role?: ExerciseRole;
  mission?: string;
  categories?: string[];
  vulnerabilities?: string[];
  tlos?: string[];
  facts?: Record<string, string>;
  entities?: Record<string, Entity>;
  events?: string[];
};

export type MinScore = {
  absolute?: number;
  percentage?: number;
};

export type Evaluation = {
  name?: string;
  description?: string;
  metrics: string[];
  min_score: MinScore;
};

export type Event = {
  name?: string;
  description?: string;
  source?: Source;
  conditions?: string[];
  injects?: string[];
};

export enum FeatureType {
  Service = 'Service',
  Configuration = 'Configuration',
  Artifact = 'Artifact',
}

export type Feature = {
  name?: string;
  description?: string;
  feature_type: FeatureType;
  source?: Source;
  dependencies?: string[];
  vulnerabilities?: string[];
  variables?: Record<string, string>;
  destination?: string;
};

export type Goal = {
  name?: string;
  description?: string;
  tlos: string[];
};

export type InfraNode = {
  name?: string;
  description?: string;
  count: number;
  links?: string[];
  dependencies?: string[];
};

export type Inject = {
  name?: string;
  description?: string;
  source?: Source;
  from_entity?: string;
  to_entities?: string[];
  tlos?: string[];
};

export enum MetricType {
  Manual = 'Manual',
  Conditional = 'Conditional',
}

export type Metric = {
  name?: string;
  description?: string;
  type: MetricType;
  artifact?: boolean;
  max_score: number;
  condition?: string;
};

export enum NodeType {
  VM = 'VM',
  Switch = 'Switch',
}

export type Resources = {
  ram: number;
  cpu: number;
};

export type Role = {
  username: string;
  entities?: string[];
};

export type Node = {
  type_field: NodeType;
  description?: string;
  resources?: Resources;
  source?: Source;
  features?: Record<string, string>;
  conditions?: Record<string, string>;
  injects?: Record<string, string>;
  vulnerabilities?: string[];
  roles?: Record<string, Role>;
};

export type Script = {
  name?: string;
  description?: string;
  start_time: bigint;
  end_time: bigint;
  speed: number;
  events: string[];
};

export type Source = {
  name: string;
  version: string;
};

export type Story = {
  name?: string;
  clock: bigint;
  scripts: string[];
};

export type TrainingLearningObjective = {
  name?: string;
  description?: string;
  evaluation: string;
};

export type Vulnerability = {
  name: string;
  description: string;
  technical: boolean;
  class: string;
};

export type Scenario = {
  name: string;
  description?: string;
  start: string;
  end: string;
  nodes?: Record<string, Node>;
  features?: Record<string, Feature>;
  infrastructure?: Record<string, InfraNode>;
  conditions?: Record<string, Condition>;
  vulnerabilities?: Record<string, Vulnerability>;
  metrics?: Record<string, Metric>;
  evaluations?: Record<string, Evaluation>;
  tlos?: Record<string, TrainingLearningObjective>;
  entities?: Record<string, Entity>;
  goals?: Record<string, Goal>;
  injects?: Record<string, Inject>;
  events?: Record<string, Event>;
  scripts?: Record<string, Script>;
  stories?: Record<string, Story>;
};

export type TloMapsByRole = {
  [key in ExerciseRole]?: Record<string, TrainingLearningObjective>};

export type ScoringMetadata = {
  startTime: string;
  endTime: string;
  entities: Record<string, Entity>;
  tlos: Record<string, TrainingLearningObjective>;
  evaluations: Record<string, Evaluation>;
  metrics: Record<string, Metric>;
};
