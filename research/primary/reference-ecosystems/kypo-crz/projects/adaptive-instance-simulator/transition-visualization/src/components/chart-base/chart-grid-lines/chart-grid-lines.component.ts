import { ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, Input } from '@angular/core';
import * as d3 from 'd3';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[chart-grid-lines]',
    templateUrl: './chart-grid-lines.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChartGridLinesComponent {
    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;

    @Input() svgWidth!: number;
    @Input() svgHeight!: number;

    private g: any;

    constructor(
        element: ElementRef,
        private ref: ChangeDetectorRef,
    ) {
        this.g = d3.select(element.nativeElement);
    }
}
