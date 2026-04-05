import {
    ChangeDetectionStrategy,
    ChangeDetectorRef,
    Component,
    ElementRef,
    EventEmitter,
    Input,
    Output,
} from '@angular/core';
import * as d3 from 'd3';
import { TrainingRunPathNode } from '../../model/training-run-path-node';
import { TransitionPhase } from '../../model/phase/transition-phase';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[phases-tasks]',
    templateUrl: './phases-tasks.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PhasesTasksComponent {
    @Input() phases!: TransitionPhase[];

    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;

    @Output() taskPreviewEvent = new EventEmitter<TrainingRunPathNode>();

    private g: any;

    constructor(
        element: ElementRef,
        private ref: ChangeDetectorRef,
    ) {
        this.g = d3.select(element.nativeElement);
    }

    getTime() {
        return new Date();
    }

    trackByPhaseId(phase: TransitionPhase) {
        return phase.id;
    }

    onTaskPreviewChange(node: TrainingRunPathNode) {
        this.taskPreviewEvent.emit(node);
    }
}
