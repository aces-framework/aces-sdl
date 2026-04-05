import { Component, Input } from '@angular/core';
import { QuestionTypeEnum } from '../../../../model/enums/question-type.enum';
import { QuestionnaireTypeEnum } from '../../../../model/enums/questionnaire-type.enum';
import { AdaptiveQuestion } from '../../../../model/phase/questionnaire-phase/adaptive-question';

@Component({
    selector: 'crczp-question-detail',
    templateUrl: './abstract-question.component.html',
    styleUrls: ['./abstract-question.component.css'],
})
export class AbstractQuestionComponent {
    @Input() question!: AdaptiveQuestion;
    @Input() questionnaireType!: QuestionnaireTypeEnum;

    readonly QuestionTypeEnum = QuestionTypeEnum;
}
