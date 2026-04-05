import { TrainingDefinitionMapper } from '@crczp/training-api';
import { InstanceModelSimulatorDTO } from '../../model/instance/instance-model-simulator-dto';
import { InstanceModelSimulator } from '../../model/instance/instance-model-simulator';
import { SankeyDataMapper } from '../../model/sankey/mapper/sankey-data-mapper';

export class InstanceSimulatorMapper {
    static fromDTO(dto: InstanceModelSimulatorDTO): InstanceModelSimulator {
        const result = new InstanceModelSimulator();
        result.trainingDefinition = TrainingDefinitionMapper.fromDTO(dto.training_definition, false, true);
        result.sankeyData = SankeyDataMapper.fromDTOs(dto.sankey_diagram);
        result.cacheId = dto.cache_key;
        return result;
    }
}
