import { Component, Input } from '@angular/core';
import { QuestionnaireTypeEnum } from '../../../../../model/enums/questionnaire-type.enum';
import { AdaptiveQuestion } from '../../../../../model/phase/questionnaire-phase/adaptive-question';

@Component({
    selector: 'crczp-free-form-question-detail',
    templateUrl: './free-form-question-detail.component.html',
    styleUrls: ['./free-form-question-detail.component.css'],
})
export class FreeFormQuestionDetailComponent {
    @Input() question!: AdaptiveQuestion;
    @Input() questionnaireType!: QuestionnaireTypeEnum;

    readonly QuestionnaireTypeEnum = QuestionnaireTypeEnum;
}
