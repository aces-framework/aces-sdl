import { UntypedFormArray, UntypedFormControl, UntypedFormGroup, Validators } from '@angular/forms';
import { DecisionMatrixRow, TrainingPhase } from '@crczp/training-model';

export class TrainingPhaseEditFormGroup {
    formGroup: UntypedFormGroup;

    constructor(phase: TrainingPhase) {
        this.formGroup = new UntypedFormGroup({
            title: new UntypedFormControl(phase.title, Validators.required),
            allowedWrongAnswers: new UntypedFormControl(phase.allowedWrongAnswers, [
                Validators.required,
                Validators.min(0),
            ]),
            allowedCommands: new UntypedFormControl(phase.allowedCommands, [Validators.required, Validators.min(0)]),
            estimatedDuration: new UntypedFormControl(phase.estimatedDuration, [
                Validators.required,
                Validators.min(0),
            ]),
            decisionMatrix: new UntypedFormArray(
                phase.decisionMatrix.map((row, index) =>
                    TrainingPhaseEditFormGroup.createRows(row, index === phase.decisionMatrix.length - 1),
                ),
            ),
        });
    }

    private static createRows(row: DecisionMatrixRow, isDisabled: boolean): UntypedFormGroup {
        return new UntypedFormGroup({
            questionnaireAnswered: new UntypedFormControl(row.questionnaireAnswered, [
                Validators.required,
                Validators.min(0),
            ]),
            completedInTime: new UntypedFormControl({ value: row.completedInTime, disabled: isDisabled }, [
                Validators.required,
                Validators.min(0),
            ]),
            keywordUsed: new UntypedFormControl({ value: row.keywordUsed, disabled: isDisabled }, [
                Validators.required,
                Validators.min(0),
            ]),
            solutionDisplayed: new UntypedFormControl({ value: row.solutionDisplayed, disabled: isDisabled }, [
                Validators.required,
                Validators.min(0),
            ]),
            wrongAnswers: new UntypedFormControl({ value: row.wrongAnswers, disabled: isDisabled }, [
                Validators.required,
                Validators.min(0),
            ]),
            order: new UntypedFormControl(row.order, [Validators.required, Validators.min(0)]),
            id: new UntypedFormControl(row.id, [Validators.required, Validators.min(0)]),
        });
    }

    setToPhase(phase: TrainingPhase): void {
        phase.title = this.formGroup.get('title').value;
        phase.allowedWrongAnswers = this.formGroup.get('allowedWrongAnswers').value;
        phase.allowedCommands = this.formGroup.get('allowedCommands').value;
        phase.estimatedDuration = this.formGroup.get('estimatedDuration').value;
        phase.decisionMatrix = this.formGroup.get('decisionMatrix').value;
        phase.valid = this.formGroup.valid;
    }
}
