import { TrainingRunData } from '../../model/training-run-data';
import { TrainingRunDataDTO } from '../../dto/training-run-data-dto';
import { TraineeMapper } from './trainee/trainee-mapper';
import { TrainingRunPathMapper } from './training-run-path/training-run-path-mapper';

/**
 * @dynamic
 */
export class TrainingRunDataMapper {
    static fromDTOs(dtos: TrainingRunDataDTO[]): TrainingRunData[] {
        return dtos.map((dto) => TrainingRunDataMapper.fromDTO(dto));
    }

    static fromDTO(dto: TrainingRunDataDTO): TrainingRunData {
        const result = new TrainingRunData();
        result.trainingRunId = dto.training_run_id;
        result.trainee = TraineeMapper.fromDTO(dto.trainee);
        result.trainingRunPathNodes = TrainingRunPathMapper.fromDTOs(dto.training_run_path_nodes);
        result.localEnvironment = dto.local_environment;
        return result;
    }
}
