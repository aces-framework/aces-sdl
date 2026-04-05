import { InfoPhaseTask } from '../../../model/phase/info-phase/info-phase-task';
import { InfoPhaseDTO } from '../../../dto/phase/info-phase/info-phase-dto';

export class InfoPhaseTaskMapper {
    static fromDTO(dto: InfoPhaseDTO): InfoPhaseTask {
        const result = new InfoPhaseTask();
        result.id = 0;
        result.order = 0;
        result.content = dto.content;
        return result;
    }
}
