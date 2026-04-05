import { ChangeDetectionStrategy, Component, ElementRef, Input } from '@angular/core';
import * as d3 from 'd3';
import { TransitionPhase } from '../../../model/phase/transition-phase';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[chart-axes]',
    templateUrl: './chart-axes.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChartAxesComponent {
    @Input() phases!: TransitionPhase[];

    @Input() xScale!: d3.ScalePoint<number>;
    @Input() yScale!: d3.ScalePoint<number>;

    @Input() svgHeight!: number;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }
}
