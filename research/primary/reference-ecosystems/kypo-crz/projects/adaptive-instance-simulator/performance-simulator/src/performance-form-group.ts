import { UntypedFormArray, UntypedFormControl, UntypedFormGroup, Validators } from '@angular/forms';
import { DecisionMatrixRow, TrainingPhase } from '@crczp/training-model';
import { TraineePhasePerformance } from './model/trainee-phase-performance';

export class PerformanceFormGroup {
    formGroup: UntypedFormGroup;

    constructor(decisionMatrix: DecisionMatrixRow[]) {
        this.formGroup = new UntypedFormGroup({
            performanceMatrix: new UntypedFormArray(decisionMatrix.map((row) => PerformanceFormGroup.createRows(row))),
        });
    }

    private static createRows(row: DecisionMatrixRow): UntypedFormGroup {
        return new UntypedFormGroup({
            questionnaireAnswered: new UntypedFormControl(false),
            solutionDisplayed: new UntypedFormControl(false),
            completionTime: new UntypedFormControl(0, [
                Validators.required,
                Validators.min(0),
                Validators.pattern('^([1-9][0-9]*)|([0])$'),
            ]),
            commandsEntered: new UntypedFormControl(0, [
                Validators.required,
                Validators.min(0),
                Validators.pattern('^([1-9][0-9]*)|([0])$'),
            ]),
            wrongAnswers: new UntypedFormControl(0, [
                Validators.required,
                Validators.min(0),
                Validators.pattern('^([1-9][0-9]*)|([0])$'),
            ]),
            order: new UntypedFormControl(row.order, [
                Validators.required,
                Validators.min(0),
                Validators.pattern('^([1-9][0-9]*)|([0])$'),
            ]),
            id: new UntypedFormControl(row.id, [
                Validators.required,
                Validators.min(0),
                Validators.pattern('^([1-9][0-9]*)|([0])$'),
            ]),
        });
    }

    setToPerformanceMatrix(traineePerformance: TraineePhasePerformance[], relatedPhases: TrainingPhase[]): void {
        (this.formGroup.get('performanceMatrix') as UntypedFormArray).controls.forEach((phasePerformance, index) => {
            traineePerformance[index].wrongAnswers = phasePerformance.get('wrongAnswers').value;
            traineePerformance[index].solutionDisplayed = phasePerformance.get('solutionDisplayed').value;
            traineePerformance[index].numberOfCommands = phasePerformance.get('commandsEntered').value;
            traineePerformance[index].phaseTime = phasePerformance.get('completionTime').value;
            traineePerformance[index].questionnaireAnswered = phasePerformance.get('questionnaireAnswered').value;
            traineePerformance[index].phaseId = relatedPhases[index].id;
        });
    }
}
