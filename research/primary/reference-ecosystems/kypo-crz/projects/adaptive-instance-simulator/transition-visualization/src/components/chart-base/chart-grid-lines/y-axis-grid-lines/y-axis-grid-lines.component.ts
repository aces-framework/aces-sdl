import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges, SimpleChanges } from '@angular/core';
import * as d3 from 'd3';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[y-axis-grid-lines]',
    templateUrl: './y-axis-grid-lines.component.html',
    styleUrls: ['./y-axis-grid-lines.component.scss'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class YAxisGridLinesComponent implements OnChanges {
    @Input() yScale!: d3.ScalePoint<number>;

    @Input() svgWidth!: number;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(changes: SimpleChanges): void {
        this.drawYGridLines();
        this.styleyGridLines();
    }

    private drawYGridLines() {
        const axisGenerator = d3.axisLeft(this.yScale).tickSize(-this.svgWidth);
        this.g.attr('id', 'y-grid-lines').attr('class', 'grid').call(axisGenerator).selectAll('text').remove();
    }

    private styleyGridLines() {
        this.g.selectAll('g').selectAll('line').attr('stroke', 'lightgrey').attr('stroke-opacity', 0.7);
        this.g.selectAll('path').attr('stroke-width', 0);
    }
}
