import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { AdaptiveQuestion, QuestionnaireTypeEnum } from '@crczp/training-model';

@Component({
    selector: 'crczp-adaptive-free-form-question-edit',
    templateUrl: './free-form-question-edit.component.html',
    styleUrls: ['./free-form-question-edit.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
/**
 * Component for editing a question of type Free Form
 */
export class FreeFormQuestionEditComponent {
    @Input() index: number;
    @Input() question: AdaptiveQuestion;
    @Input() questionnaireType: QuestionnaireTypeEnum;

    questionnaireTypes = QuestionnaireTypeEnum;
}
