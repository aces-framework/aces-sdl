import { Component, ElementRef, HostListener, Input, OnInit, ViewChild } from '@angular/core';
import * as d3 from 'd3';
import { Task } from '../../model/phase/task';
import { TransitionPhase } from '../../model/phase/transition-phase';
import { TransitionVisualizationData } from '../../model/transition-visualization-data';
import { BehaviorSubject } from 'rxjs';
import { TrainingRunPathNode } from '../../model/training-run-path-node';

@Component({
    selector: 'crczp-adaptive-transition-visualization-wrapper',
    templateUrl: './adaptive-transition-visualization-wrapper.component.html',
    styleUrls: ['./adaptive-transition-visualization-wrapper.component.scss'],
})
export class AdaptiveTransitionVisualizationWrapperComponent implements OnInit {
    @Input() data!: TransitionVisualizationData;

    @ViewChild('chart', { static: true }) private chartContainer?: ElementRef;

    @HostListener('window:resize', ['$event'])
    onResize() {
        this.setScales();
    }

    margin = { left: 80, right: 20, top: 20, bottom: 20 };

    private contentGroup: any;

    xScale!: d3.ScalePoint<number>;
    yScale!: d3.ScalePoint<number>;
    colorScale!: d3.ScaleOrdinal<string, string>;

    taskPreview$ = new BehaviorSubject<Task | undefined>(undefined);

    ngOnInit(): void {
        this.setScales();
    }

    private setScales() {
        this.initXScale();
        this.initYScale();
        this.initColorScale();
    }

    private initXScale() {
        this.xScale = d3.scalePoint();
        this.xScale
            .domain(this.data.phases.map((phase) => phase.order))
            .range([0, this.innerWidth()])
            .padding(0.4);
    }

    private initYScale() {
        this.yScale = d3.scalePoint();
        this.yScale.domain(this.getYDomain(this.data.phases)).range([this.innerHeight(), 0]).padding(0.5);
    }

    private initColorScale() {
        this.colorScale = d3.scaleOrdinal();
        this.colorScale.range(this.colors);
    }

    innerWidth(): number {
        return this.chartContainer?.nativeElement.clientWidth - this.margin.left - this.margin.right;
    }

    innerHeight(): number {
        return this.chartContainer?.nativeElement.clientHeight - this.margin.top - this.margin.bottom;
    }

    private getYDomain(phases: TransitionPhase[]): number[] {
        return [...phases]
            .sort((a: TransitionPhase, b: TransitionPhase) => b.tasks.length - a.tasks.length)[0]
            .tasks.map((task: Task) => task.order)
            .reverse();
    }

    getMarginTransform(): string {
        return `translate(${this.margin.left},${this.margin.top})`;
    }

    onTaskPreviewChange(node: TrainingRunPathNode | null) {
        const taskToPreview = this.data.phases
            .find((phase: TransitionPhase) => phase.order === node?.phaseOrder)
            ?.tasks.find((task: Task) => task.order === node?.taskOrder);
        this.taskPreview$.next(taskToPreview);
    }

    colors = [
        '#556b2f',
        '#8b4513',
        '#228b22',
        '#8b0000',
        '#808000',
        '#483d8b',
        '#008080',
        '#4682b4',
        '#9acd32',
        '#00008b',
        '#daa520',
        '#8fbc8f',
        '#8b008b',
        '#b03060',
        '#d2b48c',
        '#ff0000',
        '#00ced1',
        '#ff8c00',
        '#0000cd',
        '#00ff00',
        '#9400d3',
        '#00ff7f',
        '#dc143c',
        '#00bfff',
        '#f4a460',
        '#adff2f',
        '#b0c4de',
        '#ff00ff',
        '#1e90ff',
        '#f0e68c',
        '#fa8072',
        '#ffff54',
        '#dda0dd',
        '#7b68ee',
        '#ee82ee',
        '#98fb98',
        '#7fffd4',
        '#ff69b4',
        '#ffc0cb',
        '#696969',
    ];
}
