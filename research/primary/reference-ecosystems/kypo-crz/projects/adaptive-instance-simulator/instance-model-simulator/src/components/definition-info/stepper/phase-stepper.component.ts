import {
    ChangeDetectionStrategy,
    Component,
    EventEmitter,
    Input,
    OnChanges,
    Output,
    SimpleChanges,
} from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { SentinelStepper, StepStateEnum } from '@sentinel/components/stepper';
import { PhaseStepperAdapter } from '../../../model/adapters/phase-stepper-adapter';

/**
 * Stepper component for navigation between training-training-phase-edit definition levels
 */
@Component({
    selector: 'crczp-simulator-phase-stepper',
    templateUrl: './phase-stepper.component.html',
    styleUrls: ['./phase-stepper.component.scss'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PhaseStepperComponent implements OnChanges {
    @Input() phases: PhaseStepperAdapter[];
    @Input() movingInProgress: boolean;
    @Input() activeStep: number;

    @Output() activeStepChange: EventEmitter<number> = new EventEmitter();
    @Output() initialPhases: EventEmitter<PhaseStepperAdapter[]> = new EventEmitter();

    phaseStepper: SentinelStepper<PhaseStepperAdapter> = { items: [] };

    private previousActiveStep = -1;

    constructor(public dialog: MatDialog) {}

    ngOnChanges(changes: SimpleChanges): void {
        if ('phases' in changes) {
            this.phaseStepper.items = this.phases;
        }
        this.changeSelectedStep(this.activeStep);
    }

    /**
     * Passes active step change event to parent component
     * @param activeStep index of active (selected) phases
     */
    activeStepChanged(activeStep: number): void {
        this.activeStepChange.emit(activeStep);
    }

    private changeSelectedStep(index: number) {
        if (this.previousActiveStep >= 0 && this.previousActiveStep < this.phaseStepper.items.length) {
            this.phaseStepper.items[this.previousActiveStep].state = StepStateEnum.SELECTABLE;
        }
        this.phaseStepper.items[index].state = StepStateEnum.ACTIVE;
        this.previousActiveStep = this.activeStep;
    }
}
