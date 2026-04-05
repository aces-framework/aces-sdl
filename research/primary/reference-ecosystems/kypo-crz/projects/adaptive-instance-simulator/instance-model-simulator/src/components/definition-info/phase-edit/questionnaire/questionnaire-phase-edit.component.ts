import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { QuestionnairePhase, QuestionnaireTypeEnum, QuestionTypeEnum, TrainingPhase } from '@crczp/training-model';

@Component({
    selector: 'crczp-questionnaire-phase-configuration',
    templateUrl: './questionnaire-phase-edit.component.html',
    styleUrls: ['./questionnaire-phase-edit.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuestionnairePhaseEditComponent {
    @Input() phase: QuestionnairePhase;
    @Input() updateQuestionsFlag: boolean;
    @Input() presentTrainingPhases: TrainingPhase[];

    questionnaireTypes = QuestionnaireTypeEnum;

    getTrainingPhaseTitle(id: number): string {
        let result = '';
        result = this.presentTrainingPhases.find((phase) => phase.id === id).title;
        return result;
    }

    getQuestionTitleById(qId: number): string {
        return this.phase.questions.find((question) => question.id === qId).text;
    }

    getQuestionIconById(qId: number): string {
        switch (this.phase.questions.find((question) => question.id === qId).questionType) {
            case QuestionTypeEnum.RFQ:
                return 'star_half';
            case QuestionTypeEnum.MCQ:
                return 'check_circle_outline';
            case QuestionTypeEnum.FFQ:
                return 'edit';
        }
    }
}
