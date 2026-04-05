import { Component, Input } from '@angular/core';
import { QuestionnaireTypeEnum } from '../../../../../model/enums/questionnaire-type.enum';
import { AdaptiveQuestion } from '../../../../../model/phase/questionnaire-phase/adaptive-question';

@Component({
    selector: 'crczp-rating-form-question-detail',
    templateUrl: './rating-form-question-detail.component.html',
    styleUrls: ['./rating-form-question-detail.component.css'],
})
export class RatingFormQuestionDetailComponent {
    @Input() question!: AdaptiveQuestion;
    @Input() questionnaireType!: QuestionnaireTypeEnum;

    readonly QuestionnaireTypeEnum = QuestionnaireTypeEnum;
}
