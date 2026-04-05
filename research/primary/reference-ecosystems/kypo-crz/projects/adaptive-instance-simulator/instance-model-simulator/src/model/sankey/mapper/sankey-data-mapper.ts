import { SankeyLink } from '../sankey-link';
import { SankeyNodeDTO } from '../dto/sankey-node-dto';
import { SankeyNode } from '../sankey-node';
import { SankeyDataDTO } from '../dto/sankey-data-dto';
import { SankeyData } from '../sankey-data';

export class SankeyDataMapper {
    static fromDTOs(dto: SankeyDataDTO): SankeyData {
        const resultNodes = dto.nodes.map((nodeDTO) => this.fromDTO(nodeDTO));
        const resultLinks = dto.links.map((linkDTO) => linkDTO as SankeyLink);
        return {
            nodes: resultNodes,
            links: resultLinks,
        };
    }

    private static fromDTO(dto: SankeyNodeDTO): SankeyNode {
        return {
            taskId: dto.task_id,
            taskOrder: dto.task_order,
            taskTitle: dto.task_title,
            phaseId: dto.phase_id,
            phaseOrder: dto.phase_order,
            phaseTitle: dto.phase_title,
        };
    }
}
