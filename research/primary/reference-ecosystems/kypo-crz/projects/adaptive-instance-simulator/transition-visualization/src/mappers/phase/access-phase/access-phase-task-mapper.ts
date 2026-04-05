import { AccessPhaseDTO } from '../../../dto/phase/access-phase/access-phase-dto';
import { AccessPhaseTask } from '../../../model/phase/access-phase/access-phase-task';

export class AccessPhaseTaskMapper {
    static fromDTO(dto: AccessPhaseDTO): AccessPhaseTask {
        const result = new AccessPhaseTask();
        result.id = 0;
        result.order = 0;
        result.cloudContent = dto.cloud_content;
        result.localContent = dto.local_content;
        return result;
    }
}
