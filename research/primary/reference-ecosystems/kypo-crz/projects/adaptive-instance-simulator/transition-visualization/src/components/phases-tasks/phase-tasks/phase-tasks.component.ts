import {
    ChangeDetectionStrategy,
    ChangeDetectorRef,
    Component,
    ElementRef,
    EventEmitter,
    Input,
    OnChanges,
    Output,
    SimpleChanges,
} from '@angular/core';
import * as d3 from 'd3';
import { easeQuad } from 'd3';
import { Task } from '../../../model/phase/task';
import { TransitionPhase } from '../../../model/phase/transition-phase';
import { TrainingRunPathNode } from '../../../model/training-run-path-node';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[phase-tasks]',
    templateUrl: './phase-tasks.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PhaseTasksComponent implements OnChanges {
    @Input() phase!: TransitionPhase;

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

    ngOnChanges(changes: SimpleChanges): void {
        this.drawTaskNodesForPhase();
    }

    private drawTaskNodesForPhase(): void {
        this.g
            .selectAll('circle')
            .data(this.phase.tasks)
            .join(
                (enter: d3.Selection<any, any, any, any>) =>
                    enter.append('circle').attr('class', 'possible-task').attr('r', 4),
                (update: d3.Selection<any, any, any, any>) => update,
            )
            .attr('cx', () => {
                return this.xScale(this.phase.order);
            })
            .attr('cy', (task: Task) => {
                return this.yScale(task.order);
            })
            .attr('fill', 'lightgrey')
            .style('cursor', 'pointer')
            .on('click', (_: any, task: Task) => {
                const thisNode = new TrainingRunPathNode();
                thisNode.phaseId = this.phase.id;
                thisNode.phaseOrder = this.phase.order;
                thisNode.taskId = task.id;
                thisNode.taskOrder = task.order;
                this.taskPreviewEvent.emit(thisNode);
            })
            .on('mouseover', (event: any, task: Task) =>
                d3.select(event.target).transition().ease(easeQuad).duration(250).attr('r', 6),
            )
            .on('mouseout', (event: any, task: Task) =>
                d3.select(event.target).transition().duration(250).attr('r', 4),
            );
    }
}
