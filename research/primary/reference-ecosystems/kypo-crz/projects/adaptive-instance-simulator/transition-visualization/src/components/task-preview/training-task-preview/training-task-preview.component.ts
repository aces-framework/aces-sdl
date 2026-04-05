import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { TrainingPhaseTask } from '../../../model/phase/training-phase/training-phase-task';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'crczp-training-task-preview',
    templateUrl: './training-task-preview.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainingTaskPreviewComponent {
    @Input() task?: TrainingPhaseTask;
}
