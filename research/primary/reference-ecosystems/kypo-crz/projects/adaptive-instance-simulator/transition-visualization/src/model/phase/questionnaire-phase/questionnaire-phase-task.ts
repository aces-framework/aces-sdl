import { AdaptiveQuestion } from './adaptive-question';
import { Task } from '../task';
import { QuestionnaireTypeEnum } from '../../../model/enums/questionnaire-type.enum';

export class QuestionnairePhaseTask extends Task {
    questions!: AdaptiveQuestion[];
    questionnaireType!: QuestionnaireTypeEnum;
}
