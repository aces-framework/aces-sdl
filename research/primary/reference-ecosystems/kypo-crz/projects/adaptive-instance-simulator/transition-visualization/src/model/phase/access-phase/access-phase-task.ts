import { Task } from '../task';

export class AccessPhaseTask extends Task {
    id!: number;
    cloudContent?: string;
    localContent?: string;
}
