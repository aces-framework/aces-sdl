import { ChangeDetectionStrategy, Component, ElementRef, Input, OnChanges } from '@angular/core';
import * as d3 from 'd3';
import { TransitionPhase } from '../../../../model/phase/transition-phase';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'g[x-axis-top]',
    templateUrl: './x-axis-top.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class XAxisTopComponent implements OnChanges {
    @Input() phases!: TransitionPhase[];

    @Input() xScale!: d3.ScalePoint<number>;

    private g: any;

    constructor(element: ElementRef) {
        this.g = d3.select(element.nativeElement);
    }

    ngOnChanges(): void {
        this.drawTopXAxis();
        this.styleTopXAxis();
    }

    private drawTopXAxis() {
        const axisGenerator = d3.axisTop(this.xScale).tickFormat((phaseOrder) => this.getPhaseTitleByOrder(phaseOrder));
        // add top x axis
        this.g.attr('id', 'x-axis-top').attr('class', 'axis').call(axisGenerator);
    }

    private styleTopXAxis() {
        this.g.selectAll('g').selectAll('line').attr('stroke', 'lightgrey').attr('stroke-opacity', 0.7);
        this.g.selectAll('path').attr('stroke-width', 0);
        this.g
            .selectAll('text')
            .style('font-size', 'larger')
            .each((_: number, i: number, nodes: SVGTSpanElement[]) => {
                this.clipText(nodes[i]);
                this.addTooltip(nodes[i], this.phases[i]);
            });
    }

    private getPhaseTitleByOrder(phaseOrder: number): string {
        const phase = this.phases.find((phase: TransitionPhase) => phase.order === phaseOrder);
        return phase?.title ?? '';
    }

    // prevents overlapping of labelsTask DifficultyTask Difficulty
    clipText(textNode: SVGTSpanElement): void {
        const maxWidth = this.xScale.step();
        const textWidth = textNode.getComputedTextLength();
        const postfix = '...';
        if (textWidth > maxWidth) {
            let text = textNode.textContent as string;
            const newLength = Math.round(text.length * (1 - (textWidth - maxWidth) / textWidth)) - postfix.length - 3;
            text = text.substring(0, newLength);
            textNode.textContent = text.trim() + postfix;
        }
    }

    addTooltip(textNode: SVGTSpanElement, phase: TransitionPhase): void {
        const tooltip = d3.select('#tooltip');

        d3.select(textNode)
            .on('mouseover', () => {
                return tooltip.transition().duration(300).style('opacity', 1).style('visibility', 'visible');
            })
            .on('mousemove', (event: any) => {
                tooltip
                    .text(() => phase.title)
                    .style('top', event.offsetY + 20 + 'px')
                    .style('left', event.offsetX - (tooltip.node() as any).getBoundingClientRect().width / 2 + 'px');
                tooltip.style('visibility', 'visible');
            })
            .on('mouseout', () => {
                return tooltip.transition().duration(500).style('opacity', 0).style('visibility', 'hidden');
            });
    }
}
