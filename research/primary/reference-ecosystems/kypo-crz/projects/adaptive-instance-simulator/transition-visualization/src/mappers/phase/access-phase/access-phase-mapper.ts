import { AbstractPhaseTypeEnum } from '../../../model/enums/abstract-phase-type.enum';
import { AccessPhaseTaskMapper } from './access-phase-task-mapper';
import { AccessPhaseDTO } from '../../../dto/phase/access-phase/access-phase-dto';
import { AccessPhase } from '../../../model/phase/access-phase/access-phase';

export class AccessPhaseMapper {
    static fromDTO(dto: AccessPhaseDTO): AccessPhase {
        const result = new AccessPhase();
        result.type = AbstractPhaseTypeEnum.Access;
        result.tasks = [AccessPhaseTaskMapper.fromDTO(dto)];
        return result;
    }
}
