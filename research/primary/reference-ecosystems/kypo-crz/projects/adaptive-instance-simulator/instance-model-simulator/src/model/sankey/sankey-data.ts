import * as d3Sankey from 'd3-sankey';
import { SankeyLink } from './sankey-link';
import { SankeyNode } from './sankey-node';

type Node = d3Sankey.SankeyNode<SankeyNode, SankeyLink>;
type Link = d3Sankey.SankeyLink<SankeyNode, SankeyLink>;

export interface SankeyData {
    nodes: Node[];
    links: Link[];
}
