import { ChangeDetectionStrategy, Component, ElementRef, Input } from '@angular/core';
import * as d3 from 'd3';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[chart-axes-labels]',
    templateUrl: './chart-axes-labels.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChartAxesLabelsComponent {
    @Input() margin!: any;
    @Input() svgHeight!: number;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }
}
