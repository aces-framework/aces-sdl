import { Component, Input, OnChanges, OnInit } from '@angular/core';
import * as d3 from 'd3';
import * as d3Sankey from 'd3-sankey';
import { take } from 'rxjs/operators';
import { SankeyData } from '../../model/sankey/sankey-data';
import { SankeyDataService } from '../../service/sankey-data.service';

@Component({
    selector: 'crczp-sankey-visualization',
    templateUrl: './sankey-visualization.component.html',
    styleUrls: ['./sankey-visualization.component.css'],
})
export class SankeyVisualizationComponent implements OnInit, OnChanges {
    /**
     * Flag to use local mock
     */
    @Input() useMockLoad = false;
    /**
     * Id of training instance
     */
    @Input() trainingInstanceId: number;
    /**
     * Data for sankey graph
     */
    @Input() graphData: SankeyData;
    /**
     * The width of the diagram
     */
    @Input() svgWidth = 960;
    /**
     * The height of the diagram
     */
    @Input() svgHeight = 500;

    data: SankeyData;

    private svg: d3.Selection<d3.BaseType, unknown, HTMLElement, unknown>;
    private links: d3.Selection<d3.BaseType, unknown, SVGGElement, unknown>;
    private nodes: d3.Selection<null, undefined, SVGGElement, unknown>;
    private color = d3.scaleOrdinal(d3.schemeCategory10);

    constructor(private sankeyDataService: SankeyDataService) {}

    ngOnInit(): void {
        if (this.graphData) {
            this.data = this.graphData;
            this.drawChart();
        } else {
            this.load();
        }
    }

    ngOnChanges() {
        if (this.graphData) {
            this.data = this.graphData;
            this.drawChart();
        }
    }

    private load() {
        this.sankeyDataService
            .getAllData(this.trainingInstanceId)
            .pipe(take(1))
            .subscribe((data: SankeyData) => {
                this.data = data;
                this.drawChart();
            });
    }

    private drawChart() {
        d3.selectAll('svg > *').remove();
        this.svg = d3.select('#sankey');
        this.svg.attr('width', this.svgWidth);
        this.svg.attr('height', this.svgHeight);

        const sankey = d3Sankey
            .sankey()
            .nodeWidth(15)
            .nodePadding(20)
            .nodeSort(null)
            .extent([
                [20, 20],
                [this.svgWidth - 50, this.svgHeight - 6],
            ]);

        sankey(this.data);
        this.renderLinks();
        this.renderNodes();
    }

    private renderNodes() {
        this.nodes = this.createContainerForNodes();
        const node = this.createContainerForSingleNode();
        this.renderNodeRectangle(node);
        this.renderTextForEachNode(node);
        this.renderTextAboveEachNode(node);
    }

    private renderLinks() {
        this.links = this.createContainerForLinks();
        const link = this.createContainerForSingleLink();
        this.attachMouseOverEventOnLink(link);
        this.attachMouseOutEventOnLink(link);
        this.renderLinkPath(link);
        this.renderLinkText(link);
    }

    private createContainerForNodes() {
        return this.svg
            .append('g')
            .attr('class', 'nodes')
            .attr('font-family', 'Inter, sans-serif')
            .attr('font-size', 12)
            .selectAll();
    }

    private createContainerForSingleNode() {
        return this.nodes.data(this.data.nodes).enter().append('g');
    }

    private renderNodeRectangle(node: any) {
        node.append('rect')
            .attr('x', (n: any) => n.x0)
            .attr('y', (n: any) => n.y0)
            .attr('height', (n: any) => n.y1 - n.y0)
            .attr('width', (n: any) => n.x1 - n.x0)
            .attr('fill', (n: any) => this.color(n.phaseId + n.taskId));
    }

    private renderTextForEachNode(node: any) {
        node.append('text')
            .filter((n: any) => n.phaseOrder > 0)
            .attr('x', (n: any) => n.x1 + 6)
            .attr('y', (n: any) => (n.y1 + n.y0) / 2)
            .attr('dy', '0.35em')
            .text((n: any) => (n.taskOrder === null ? '' : 'Task ' + (n.taskOrder + 1)))
            .attr('text-anchor', 'start');
    }

    private renderTextAboveEachNode(node: any) {
        const drawnPhases = [];
        node.append('text')
            .filter((n: any) => {
                if (!drawnPhases.includes(n.phaseOrder)) {
                    drawnPhases.push(n.phaseOrder);
                    return true;
                }
            })
            .attr('x', (n: any) => {
                if (n.phaseOrder === -1) {
                    return 30;
                } else {
                    return n.x0 + 10;
                }
            })
            .attr('y', 10)
            .attr('font-family', 'Inter, sans-serif')
            .attr('fill', 'Black')
            .style('font', 'bold 12px Arial')
            .attr('text-anchor', 'middle')
            .text((n: any, i: any) => {
                if (n.phaseOrder === -1) {
                    return 'START';
                } else if (n.phaseOrder === -2) {
                    return 'FINISH';
                }
                return 'Training Phase ' + i;
            });
    }

    private createContainerForLinks() {
        return this.svg
            .append('g')
            .attr('class', 'links')
            .attr('fill', 'none')
            .attr('stroke-opacity', 0.2)
            .selectAll('path');
    }

    private attachMouseOverEventOnLink(link: any) {
        link.on('mouseover', (event, l) => {
            d3.select(event.currentTarget).attr('stroke-opacity', 0.6);
            d3.select(event.currentTarget).select('text').style('font', 'bold 16px Arial');
        }).selectAll('path');
    }

    private attachMouseOutEventOnLink(link: any) {
        link.on('mouseout', (event, l) => {
            d3.select(event.currentTarget).attr('stroke-opacity', 0.2);
            d3.select(event.currentTarget).select('text').style('font', 'normal 12px Arial');
        }).selectAll('path');
    }

    private createContainerForSingleLink() {
        return this.links.data(this.data.links).enter().append('g');
    }

    private renderLinkPath(link: any) {
        link.append('path')
            .attr('d', d3Sankey.sankeyLinkHorizontal())
            .attr('stroke', (l: any) => this.color(l.source.phaseId + l.source.taskId))
            .attr('stroke-width', (l: any) => Math.max(0, l.width));
    }

    private renderLinkText(link: any) {
        link.append('text')
            .filter((l: any) => l.value !== 0)
            .attr('font-family', 'Inter, sans-serif')
            .attr('fill', 'Black')
            .style('font', 'normal 12px Arial')
            .attr('dy', (l: any) => 6 + l.y0 + (l.y1 - l.y0) / 2)
            .attr('dx', (l: any) => l.source.x1 + (l.target.x0 - l.source.x1) / 2)
            .attr('text-anchor', 'middle')
            .text((l) => (l.modified ? l.value - 1 : l.value));
    }
}
