import { AbstractPhaseTypeEnum } from '../enums/abstract-phase-type.enum';
import { Task } from './task';

export abstract class TransitionPhase {
    id!: number;
    title!: string;
    order!: number;
    type!: AbstractPhaseTypeEnum;
    tasks!: Task[];
}
