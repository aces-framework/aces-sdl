import { ChangeDetectionStrategy, Component, ElementRef, Input, OnInit } from '@angular/core';
import * as d3 from 'd3';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[y-axis-left-label]',
    templateUrl: './y-axis-left-label.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class YAxisLeftLabelComponent implements OnInit {
    // TODO: add margin type
    @Input() margin: any;
    @Input() svgHeight!: number;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnInit(): void {
        this.drawYAxisLabel();
    }

    private drawYAxisLabel() {
        this.g
            .append('text')
            .attr('transform', 'rotate(-90)')
            .attr('y', -this.margin.left)
            .attr('x', -this.svgHeight / 2)
            .attr('dy', '1em')
            .style('text-anchor', 'middle')
            .text('Task Difficulty')
            .style('font-size', 'larger');
    }
}
