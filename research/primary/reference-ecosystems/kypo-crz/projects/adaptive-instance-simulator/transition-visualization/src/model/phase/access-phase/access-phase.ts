import { AccessPhaseTask } from './access-phase-task';
import { TransitionPhase } from '../transition-phase';

export class AccessPhase extends TransitionPhase {
    tasks!: AccessPhaseTask[];
}
