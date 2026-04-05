import { TransitionPhase } from '../transition-phase';
import { InfoPhaseTask } from './info-phase-task';

export class InfoPhase extends TransitionPhase {
    tasks!: InfoPhaseTask[];
}
