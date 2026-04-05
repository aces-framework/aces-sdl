import { SankeyNodeDTO } from './sankey-node-dto';
import { SankeyLinkDTO } from './sankey-link-dto';

export interface SankeyDataDTO {
    nodes: SankeyNodeDTO[];
    links: SankeyLinkDTO[];
}
