import { TransitionPhase } from '../transition-phase';
import { QuestionnaireTypeEnum } from '../../enums/questionnaire-type.enum';
import { QuestionnairePhaseTask } from './questionnaire-phase-task';

export class QuestionnairePhase extends TransitionPhase {
    questionnaireType!: QuestionnaireTypeEnum;
    tasks!: QuestionnairePhaseTask[];
}
