import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges, SimpleChanges } from '@angular/core';
import * as d3 from 'd3';
import { TrainingRunData } from '../../../../model/training-run-data';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[training-run-path]',
    templateUrl: './training-run-path.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerPathComponent implements OnChanges {
    @Input() playerTransitions!: TrainingRunData;

    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;

    @Input() color!: string;

    private g: any;
    private duration = 1000;
    private pathLength = 0;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(changes: SimpleChanges): void {
        if ('xScale' in changes && !changes.xScale.isFirstChange()) {
            this.duration = 0;
            this.drawPath(false);
            this.duration = 1000;
        } else this.drawPath();
    }

    drawPath(animate = true) {
        this.g
            .selectAll('path')
            .data([this.playerTransitions])
            .join((enter: d3.Selection<any, any, any, any>) => enter.append('path'))
            .attr('d', this.createPathString())
            .call((selection: any) => {
                this.addStyle(selection);
                if (animate) this.animatePathGrow(selection);
                this.setPathLength(selection);
            });
    }

    createPathString(): string {
        return (
            d3.line().curve(d3.curveBumpX)(
                this.playerTransitions.trainingRunPathNodes.map((playerPath: any) => [
                    this.xScale(playerPath.phaseOrder) as number,
                    this.yScale(playerPath.taskOrder) as number,
                ]),
            ) ?? ''
        );
    }

    private addStyle(newPath: any) {
        newPath.attr('stroke', this.color).attr('stroke-width', 5).attr('fill', 'none');
    }

    private animatePathGrow(newPath: d3.Selection<d3.BaseType, unknown, any, any>): d3.Transition<any, any, any, any> {
        let oldPathLength = this.pathLength;

        // TODO: decide if worth
        if (Number.parseFloat(newPath.attr('stroke-dashoffset')) > 0) {
            oldPathLength -= Number.parseFloat(newPath.attr('stroke-dashoffset'));
        }

        const newPathLength = this.getPathLength(newPath);

        return newPath
            .interrupt()
            .attr('stroke-dasharray', newPathLength + ' ' + newPathLength)
            .attr('stroke-dashoffset', Math.abs(newPathLength - oldPathLength))
            .transition()
            .ease(d3.easeLinear)
            .duration(this.duration)
            .attr('stroke-dashoffset', () => 0);
    }

    private getPathLength(path: d3.Selection<any, any, any, any>): number {
        return path.node().getTotalLength();
    }

    private setPathLength(selection: d3.Selection<any, any, any, any>) {
        this.pathLength = this.getPathLength(selection);
    }
}
