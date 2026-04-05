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
import { TrainingRunData } from '../../model/training-run-data';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[training-runs-transitions]',
    templateUrl: './training-runs-transitions.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayersTransitionsComponent {
    @Input() playersTransitions!: TrainingRunData[];

    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;
    @Input() colorScale!: d3.ScaleOrdinal<string, string>;

    @Output() taskPreviewEvent = new EventEmitter<TrainingRunPathNode>();

    private g: any;

    constructor(
        element: ElementRef,
        private ref: ChangeDetectorRef,
    ) {
        this.g = d3.select(element.nativeElement);
    }

    trackByTrainingRunId(playerData: TrainingRunData) {
        return playerData.trainingRunId;
    }

    onTaskPreviewChange(node: TrainingRunPathNode) {
        this.taskPreviewEvent.emit(node);
    }
}
