import { Component, EventEmitter, Input, Output } from '@angular/core';
import { AdaptiveQuestion, QuestionnaireTypeEnum } from '@crczp/training-model';

@Component({
    selector: 'crczp-adaptive-multiple-choice-question-edit',
    templateUrl: './multiple-choice-question-edit.component.html',
    styleUrls: ['./multiple-choice-question-edit.component.css'],
})
/**
 * Component for editing a question of type Multiple Choice
 */
export class MultipleChoiceQuestionEditComponent {
    @Input() index: number;
    @Input() question: AdaptiveQuestion;
    @Input() questionnaireType: QuestionnaireTypeEnum;
    @Output() questionChange: EventEmitter<AdaptiveQuestion> = new EventEmitter();

    questionnaireTypes = QuestionnaireTypeEnum;
}
