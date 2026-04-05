import { QuestionTypeEnum } from '../../enums/question-type.enum';
import { Choice } from './choice';

export class AdaptiveQuestion {
    id!: number;
    order!: number;
    text!: string;
    valid: boolean;
    questionType!: QuestionTypeEnum;
    choices!: Choice[];

    constructor() {
        this.valid = true;
    }
}
