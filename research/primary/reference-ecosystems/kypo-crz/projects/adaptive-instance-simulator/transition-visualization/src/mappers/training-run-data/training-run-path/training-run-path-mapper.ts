import { TrainingRunPathNode } from '../../../model/training-run-path-node';
import { TrainingRunPathNodeDTO } from '../../../dto/training-run-path-node-dto';

export class TrainingRunPathMapper {
    static fromDTOs(dtos: TrainingRunPathNodeDTO[]): TrainingRunPathNode[] {
        return dtos.map((dto) => TrainingRunPathMapper.fromDTO(dto));
    }

    static fromDTO(dto: TrainingRunPathNodeDTO): TrainingRunPathNode {
        const result = new TrainingRunPathNode();
        result.phaseId = dto.phase_id;
        result.phaseOrder = dto.phase_order;
        result.taskId = dto.task_id;
        result.taskOrder = dto.task_order;
        return result;
    }
}
