import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { AdaptiveQuestion, QuestionnaireTypeEnum, QuestionTypeEnum } from '@crczp/training-model';

@Component({
    selector: 'crczp-adaptive-question-edit',
    templateUrl: './question-edit.component.html',
    styleUrls: ['./question-edit.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuestionEditComponent {
    @Input() question: AdaptiveQuestion;
    @Input() questionnaireType: QuestionnaireTypeEnum;
    @Input() index: number;

    questionTypes = QuestionTypeEnum;
}
