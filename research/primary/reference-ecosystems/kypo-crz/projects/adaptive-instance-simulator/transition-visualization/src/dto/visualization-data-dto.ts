import { AbstractPhaseDTO } from './phase/abstract-phase-dto';
import { TrainingRunDataDTO } from './training-run-data-dto';

export interface VisualizationDataDTO {
    phases: AbstractPhaseDTO[];
    training_runs_data: TrainingRunDataDTO[];
}
