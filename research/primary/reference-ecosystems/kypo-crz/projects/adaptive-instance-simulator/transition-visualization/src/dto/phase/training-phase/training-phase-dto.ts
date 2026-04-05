import { AbstractPhaseDTO } from '../abstract-phase-dto';
import { TaskDTO } from './task-dto';

export interface TrainingPhaseDTO extends AbstractPhaseDTO {
    allowed_wrong_answers: number;
    allowed_commands: number;
    estimated_duration: number;
    tasks: TaskDTO[];
}
