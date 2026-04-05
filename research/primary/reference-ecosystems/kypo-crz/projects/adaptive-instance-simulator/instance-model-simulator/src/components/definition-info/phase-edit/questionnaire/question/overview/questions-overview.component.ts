import { Component, Input, OnChanges, OnInit, SimpleChanges } from '@angular/core';
import { SentinelStepper } from '@sentinel/components/stepper';
import { SentinelControlItem } from '@sentinel/components/controls';

import { MatDialog } from '@angular/material/dialog';
import { AdaptiveQuestionStepperAdapter } from '../../../../../../model/adapters/adaptive-question-stepper-adapter';
import { AdaptiveQuestion, QuestionnaireTypeEnum } from '@crczp/training-model';

@Component({
    selector: 'crczp-adaptive-questions-overview',
    templateUrl: './questions-overview.component.html',
    styleUrls: ['./questions-overview.component.css'],
})
export class QuestionsOverviewComponent implements OnInit, OnChanges {
    @Input() questions: AdaptiveQuestion[];
    @Input() questionnaireOrder: number;
    @Input() questionnaireType: QuestionnaireTypeEnum;

    stepperQuestions: SentinelStepper<AdaptiveQuestionStepperAdapter> = { items: [] };
    controls: SentinelControlItem[];
    selectedStep: number;

    constructor(public dialog: MatDialog) {}

    ngOnInit(): void {
        this.selectedStep = 0;
    }

    ngOnChanges(changes: SimpleChanges): void {
        if (
            changes['questionnaireOrder'] &&
            changes['questionnaireOrder'].previousValue !== changes['questionnaireOrder'].currentValue
        ) {
            this.selectedStep = 0;
        }
        if ('questions' in changes && changes['questions'].isFirstChange()) {
            this.selectedStep = 0;
        }
        if ('questions' in changes && this.questions) {
            this.stepperQuestions.items = this.questions.map(
                (question) => new AdaptiveQuestionStepperAdapter(question),
            );
        }
        if (this.stepperQuestions.items.length > 0) {
            this.stepperQuestions.items[this.selectedStep].isActive = true;
        }
    }

    /**
     * Triggered after selection of active question is changed in the stepper
     * @param index index of active question
     */
    onActiveQuestionChanged(index: number): void {
        if (index !== this.selectedStep && this.stepperQuestions.items.length > 0) {
            this.stepperQuestions.items[this.selectedStep].isActive = false;
            this.selectedStep = index;
        }
    }
}
