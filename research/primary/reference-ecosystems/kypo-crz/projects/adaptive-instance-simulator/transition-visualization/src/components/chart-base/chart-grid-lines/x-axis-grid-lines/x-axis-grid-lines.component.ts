import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges, SimpleChanges } from '@angular/core';
import * as d3 from 'd3';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[x-axis-grid-lines]',
    templateUrl: './x-axis-grid-lines.component.html',
    styleUrls: ['./x-axis-grid-lines.component.scss'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class XAxisGridLinesComponent implements OnChanges {
    @Input() xScale!: d3.ScalePoint<number>;

    @Input() svgHeight!: number;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(changes: SimpleChanges): void {
        this.drawXGridLines();
        this.styleXGridLines();
    }

    private drawXGridLines(): any {
        const axisGenerator = d3.axisBottom(this.xScale).tickSize(-this.svgHeight);
        this.g
            .attr('id', 'x-grid-lines')
            .attr('class', 'grid')
            .attr('transform', 'translate(0,' + this.svgHeight + ')')
            .call(axisGenerator)
            .selectAll('text')
            .remove();
    }

    private styleXGridLines() {
        this.g.selectAll('g').selectAll('line').attr('stroke', 'lightgrey').attr('stroke-opacity', 0.7);
        this.g.selectAll('path').attr('stroke-width', 0);
    }
}
