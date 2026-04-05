import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges, SimpleChanges } from '@angular/core';
import * as d3 from 'd3';
import { TransitionPhase } from '../../../../model/phase/transition-phase';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[y-axis-left]',
    templateUrl: './y-axis-left.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class YAxisLeftComponent implements OnChanges {
    @Input() phases!: TransitionPhase[];

    @Input() yScale!: d3.ScalePoint<number>;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(changes: SimpleChanges): void {
        this.drawYAxis();
        this.styleLeftYAxis();
    }

    private drawYAxis() {
        const axisGenerator = d3.axisLeft(this.yScale).tickFormat((taskId) => `Task ${taskId + 1}`);
        // add y axis
        this.g.attr('id', 'y-axis').attr('class', 'axis').call(axisGenerator);
    }

    private styleLeftYAxis() {
        this.g.selectAll('g').selectAll('line').attr('stroke', 'lightgrey').attr('stroke-opacity', 0.7);
        this.g.selectAll('path').attr('stroke-width', 0);
        this.g.selectAll('text').style('font-size', 'larger');
    }
}
