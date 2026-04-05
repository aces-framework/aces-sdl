import { Trainee } from './trainee';
import { TrainingRunPathNode } from './training-run-path-node';

export class TrainingRunData {
    trainingRunId!: number;
    trainee!: Trainee;
    trainingRunPathNodes!: TrainingRunPathNode[];
    localEnvironment!: boolean;
}
