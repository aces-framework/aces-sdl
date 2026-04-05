import { Component, Input } from '@angular/core';
import { QuestionnaireTypeEnum } from '../../../../../model/enums/questionnaire-type.enum';
import { AdaptiveQuestion } from '../../../../../model/phase/questionnaire-phase/adaptive-question';

@Component({
    selector: 'crczp-multiple-choice-question-detail',
    templateUrl: './multiple-choice-question-detail.component.html',
    styleUrls: ['./multiple-choice-question-detail.component.css'],
})
export class MultipleChoiceQuestionDetailComponent {
    @Input() question!: AdaptiveQuestion;
    @Input() questionnaireType!: QuestionnaireTypeEnum;

    readonly QuestionnaireTypeEnum = QuestionnaireTypeEnum;
}
