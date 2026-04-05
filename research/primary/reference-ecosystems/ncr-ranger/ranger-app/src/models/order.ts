
type NewOrder = {
  name: string;
  clientId: string;
  status: OrderStatus;
};

type UpdateOrder = {
  status: OrderStatus;
};

enum OrderStatus {
  DRAFT = 'draft',
  REVIEW = 'review',
  INPROGRESS = 'inProgress',
  READY = 'ready',
  FINISHED = 'finished',
}

type NewThreat = {
  threat: string;
};

type Threat = NewThreat & {
  id: string;
};

type NewTrainingObjective = {
  objective: string;
  threats: NewThreat[];
};

type TrainingObjective = Omit<NewTrainingObjective, 'threats'> & {
  id: string;
  threats: Threat[];
};

type NewSkill = {
  skill: string;
};

type Skill = NewSkill & {
  id: string;
};

type NewTrainingObjectiveConnection = {
  trainingObjectiveId: string;
};

type TrainingObjectiveConnection = NewTrainingObjectiveConnection & {
  id: string;
};

type NewWeakness = {
  weakness: string;
};

type Weakness = NewWeakness & {
  id: string;
};

type NewStructure = {
  name: string;
  description?: string;
  parentId?: string;
  skills?: NewSkill[];
  trainingObjectiveIds?: NewTrainingObjectiveConnection[];
  weaknesses?: NewWeakness[];
};

type Structure = Omit<NewStructure, 'skills' | 'weaknesses' | 'trainingObjectiveIds' > & {
  id: string;
  skills?: Skill[];
  trainingObjectiveIds?: TrainingObjectiveConnection[];
  weaknesses?: Weakness[];
};

type NewStrength = {
  strength: string;
};

type Strength = NewStrength & {
  id: string;
};

type NewEnvironment = {
  name: string;
  category: string;
  size: number;
  additionalInformation?: string;
  weaknesses?: NewWeakness[];
  strengths?: NewStrength[];
};

type Environment = Omit<NewEnvironment, 'weaknesses' | 'strengths'> & {
  id: string;
  weaknesses?: Weakness[];
  strengths?: Strength[];
};

type NewCustomElement = {
  name: string;
  description: string;
  environmentId: string;
};

type CustomElement = NewCustomElement & {
  id: string;
};

type NewStructureConnection = {
  structureId: string;
};

type StructureConnection = NewStructureConnection & {
  id: string;
};

type NewPlotPoint = {
  name: string;
  description: string;
  objectiveId: string;
  triggerTime: string;
  structureIds: NewStructureConnection[];
};

type PlotPoint = Omit<NewPlotPoint, 'structureIds'> & {
  id: string;
  structureIds: StructureConnection[];
};

type NewPlot = {
  name: string;
  description: string;
  startTime: string;
  endTime: string;
  plotPoints: NewPlotPoint[];
};

type Plot = Omit<NewPlot, 'plotPoints'> & {
  id: string;
  plotPoints: PlotPoint[];
};

type Order = {
  id: string;
  trainingObjectives?: TrainingObjective[];
  structures?: Structure[];
  environments?: Environment[];
  customElements?: CustomElement[];
  plots?: Plot[];
  createdAt: string;
  updatedAt: string;
} & NewOrder;

export type {
  NewStructure,
  Structure,
  NewTrainingObjective,
  NewOrder,
  UpdateOrder,
  Order,
  TrainingObjective,
  Skill,
  NewSkill,
  Weakness,
  NewWeakness,
  Strength,
  NewStrength,
  Environment,
  NewEnvironment,
  TrainingObjectiveConnection,
  NewTrainingObjectiveConnection,
  NewCustomElement,
  CustomElement,
  StructureConnection,
  NewStructureConnection,
  PlotPoint,
  NewPlotPoint,
  Plot,
  NewPlot,
};

export {OrderStatus};
