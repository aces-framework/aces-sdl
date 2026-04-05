import { TransitionPhase } from '../transition-phase';
import { TrainingPhaseTask } from './training-phase-task';

export class TrainingPhase extends TransitionPhase {
    allowedWrongAnswers!: number;
    allowedCommands!: number;
    estimatedDuration!: number;
    tasks!: TrainingPhaseTask[];
}
