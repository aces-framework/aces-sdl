import { TrainingPhaseTask } from '../../../model/phase/training-phase/training-phase-task';
import { TaskDTO } from '../../../dto/task-dto';

export class TrainingPhaseTaskMapper {
    static fromDTOs(dtos: TaskDTO[]): TrainingPhaseTask[] {
        return dtos.map((dto) => TrainingPhaseTaskMapper.fromDTO(dto));
    }

    static fromDTO(dto: TaskDTO): TrainingPhaseTask {
        const result = new TrainingPhaseTask();
        result.id = dto.id;
        result.order = dto.order;
        result.answer = dto.answer;
        result.content = dto.content;
        result.solution = dto.solution;
        return result;
    }
}
