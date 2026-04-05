import { InfoPhase } from '../../../model/phase/info-phase/info-phase';
import { InfoPhaseDTO } from '../../../dto/phase/info-phase/info-phase-dto';
import { AbstractPhaseTypeEnum } from '../../../model/enums/abstract-phase-type.enum';
import { InfoPhaseTaskMapper } from './info-phase-task-mapper';

export class InfoPhaseMapper {
    static fromDTO(dto: InfoPhaseDTO): InfoPhase {
        const result = new InfoPhase();
        result.type = AbstractPhaseTypeEnum.Info;
        result.tasks = [InfoPhaseTaskMapper.fromDTO(dto)];
        return result;
    }
}
