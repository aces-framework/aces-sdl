import {
    ChangeDetectionStrategy,
    Component,
    DestroyRef,
    EventEmitter,
    inject,
    Input,
    OnChanges,
    Output,
    SimpleChanges,
} from '@angular/core';
import { UntypedFormArray } from '@angular/forms';
import { PerformanceFormGroup } from './performance-form-group';
import { DecisionMatrixRow, TrainingPhase } from '@crczp/training-model';
import { TraineePhasePerformance } from './model/trainee-phase-performance';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

@Component({
    selector: 'crczp-performance-simulator',
    templateUrl: './performance.component.html',
    styleUrls: ['./performance.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PerformanceComponent implements OnChanges {
    @Input() phase: TrainingPhase;
    @Input() relatedPhases: TrainingPhase[];
    @Output() matrixChange: EventEmitter<TraineePhasePerformance[]> = new EventEmitter();
    @Output() startGenerate: EventEmitter<void> = new EventEmitter();

    destroyRef = inject(DestroyRef);

    performanceFormGroup: PerformanceFormGroup;
    traineePerformance: TraineePhasePerformance[] = [];

    get decisionMatrixRows(): UntypedFormArray {
        return this.performanceFormGroup.formGroup.get('performanceMatrix') as UntypedFormArray;
    }

    ngOnChanges(changes: SimpleChanges): void {
        if ('phase' in changes) {
            this.performanceFormGroup = new PerformanceFormGroup(this.phase.decisionMatrix);
            this.setFormsAsTouched();
            this.performanceFormGroup.formGroup.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
                this.createPerformanceMatrix(this.phase.decisionMatrix);
                this.performanceFormGroup.setToPerformanceMatrix(this.traineePerformance, this.relatedPhases);
                this.matrixChange.emit(this.traineePerformance);
            });
        }
    }

    generate(): void {
        this.startGenerate.emit();
    }

    private createPerformanceMatrix(decisionMatrix: DecisionMatrixRow[]): TraineePhasePerformance[] {
        this.traineePerformance = [];
        decisionMatrix.forEach(() => {
            this.traineePerformance.push(new TraineePhasePerformance());
        });
        return this.traineePerformance;
    }

    private setFormsAsTouched(): void {
        this.decisionMatrixRows.markAllAsTouched();
    }
}
