import { TraineeDTO } from './trainee-dto';
import { TrainingRunPathNodeDTO } from './training-run-path-node-dto';

export interface TrainingRunDataDTO {
    training_run_id: number;
    trainee: TraineeDTO;
    training_run_path_nodes: TrainingRunPathNodeDTO[];
    local_environment: boolean;
}
