import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { AdaptiveQuestion, QuestionnaireTypeEnum } from '@crczp/training-model';

@Component({
    selector: 'crczp-rating-form-question-edit',
    templateUrl: './rating-form-question-edit.component.html',
    styleUrls: ['./rating-form-question-edit.component.css'],
})
/**
 * Component for editing a question of type Rating Form
 */
export class RatingFormQuestionEditComponent implements OnChanges {
    @Input() index: number;
    @Input() question: AdaptiveQuestion;
    @Input() questionnaireType: QuestionnaireTypeEnum;

    questionnaireTypes = QuestionnaireTypeEnum;
    selectedRatingLevel: number;
    ratingLevelOptions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

    ngOnChanges(changes: SimpleChanges): void {
        if ('question' in changes) {
            this.selectedRatingLevel = this.question.choices.length;
        }
    }
}
