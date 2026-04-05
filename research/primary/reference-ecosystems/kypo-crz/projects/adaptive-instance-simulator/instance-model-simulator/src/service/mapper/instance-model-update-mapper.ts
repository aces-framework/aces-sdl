import { PhaseMapper } from '@crczp/training-api';
import { Phase } from '@crczp/training-model';
import { InstanceModelSimulator } from '../../model/instance/instance-model-simulator';
import { InstanceModelUpdateDTO } from '../../model/instance/instance-model-update-dto';

export class InstanceModelUpdateMapper {
    static toUpdateDTO(data: InstanceModelSimulator): InstanceModelUpdateDTO {
        const dto = new InstanceModelUpdateDTO();
        dto.phases = PhaseMapper.toUpdateDTOs(data.trainingDefinition.levels as Phase[]);
        dto.cache_id = data.cacheId;

        return dto;
    }
}
