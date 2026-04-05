import { VisualizationDataDTO } from '../dto/visualization-data-dto';
import { TransitionVisualizationData } from '../model/transition-visualization-data';
import { PhaseMapper } from './phase/phase-mapper';
import { TrainingRunDataMapper } from './training-run-data/training-run-data-mapper';

export class VisualizationDataMapper {
    static fromDTO(dto: VisualizationDataDTO): TransitionVisualizationData {
        const visualizationData = new TransitionVisualizationData();
        visualizationData.phases = PhaseMapper.fromDTOs(dto.phases);
        visualizationData.trainingRunsData = TrainingRunDataMapper.fromDTOs(dto.training_runs_data);

        return visualizationData;
    }
}
