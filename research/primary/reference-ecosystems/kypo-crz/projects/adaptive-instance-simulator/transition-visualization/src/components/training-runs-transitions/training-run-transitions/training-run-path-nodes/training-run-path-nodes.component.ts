import {
    ChangeDetectionStrategy,
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
import { TrainingRunPathNode } from '../../../../model/training-run-path-node';
import { TrainingRunData } from '../../../../model/training-run-data';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[training-run-path-nodes]',
    templateUrl: './training-run-path-nodes.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerPathNodesComponent implements OnChanges {
    @Input() playerTransitions!: TrainingRunData;

    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;

    @Input() color!: string;

    @Output() taskPreviewEvent = new EventEmitter<TrainingRunPathNode>();

    private g: any;
    private duration = 1000;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(changes: SimpleChanges): void {
        this.drawPathNodes();
    }

    drawPathNodes() {
        this.g
            .selectAll('circle')
            .data(
                this.playerTransitions.trainingRunPathNodes,
                (playerPathNode: TrainingRunPathNode) => playerPathNode.phaseOrder,
            )
            .join(
                (enter: d3.Selection<any, any, any, any>) => this.appendPathNodes(enter),
                (update: d3.Selection<any, any, any, any>) => this.updatePathNodes(update),
            );
    }

    private appendPathNodes(enterSelection: d3.Selection<any, any, any, any>): d3.Selection<any, any, any, any> {
        return enterSelection.append('circle').call((selection: d3.Selection<any, any, any, any>) => {
            this.addStyle(selection);
            this.animateCircleGrow(selection);
            this.setPosition(selection);
            this.addHoverAnimation(selection);
            this.addClickEvent(selection);
        });
    }

    private updatePathNodes(updateSelection: d3.Selection<any, any, any, any>): d3.Selection<any, any, any, any> {
        return updateSelection.call((selection: d3.Selection<any, any, any, any>) => {
            this.setPosition(selection);
        });
    }

    private addStyle(newPath: any): void {
        newPath.attr('stroke', this.color).attr('stroke-width', 5).attr('fill', this.color).style('cursor', 'pointer');
    }

    private animateCircleGrow(circles: d3.Selection<d3.BaseType, unknown, any, any>): void {
        circles
            .interrupt()
            .attr('r', 0)
            .transition()
            .ease(d3.easeLinear)
            .duration(this.duration / circles.nodes().length)
            .delay((_, i) => {
                return Math.min((this.duration / circles.nodes().length) * i, this.duration);
            })
            .attr('r', 6);
    }

    private setPosition(playerPathNodeSelection: d3.Selection<any, any, any, any>): void {
        playerPathNodeSelection
            .attr('cx', (playerPathNode: TrainingRunPathNode) => this.xScale(playerPathNode.phaseOrder) as number)
            .attr('cy', (playerPathNode: TrainingRunPathNode) => this.yScale(playerPathNode.taskOrder) as number);
    }

    private addHoverAnimation(circles: d3.Selection<d3.BaseType, unknown, any, any>) {
        circles
            .on('mouseover', (event: any) =>
                d3.select(event.target).transition().ease(easeQuad).duration(250).attr('r', 8),
            )
            .on('mouseout', (event: any) => d3.select(event.target).transition().duration(250).attr('r', 6));
    }

    private addClickEvent(circles: d3.Selection<d3.BaseType, TrainingRunPathNode, any, any>) {
        circles.on('click', (_: any, playerPathNode: TrainingRunPathNode) => {
            this.taskPreviewEvent.emit(playerPathNode);
        });
    }
}
