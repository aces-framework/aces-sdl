import { AbstractPhaseDTO } from '../../dto/phase/abstract-phase-dto';
import { TrainingPhaseMapper } from './training-phase/training-phase-mapper';
import { TrainingPhaseDTO } from '../../dto/phase/training-phase/training-phase-dto';
import { InfoPhaseMapper } from './info-phase/info-phase-mapper';
import { InfoPhaseDTO } from '../../dto/phase/info-phase/info-phase-dto';
import { QuestionnairePhaseMapper } from './questionnaire-phase/questionnaire-phase-mapper';
import { QuestionnairePhaseDTO } from '../../dto/phase/questionnaire-phase/questionnaire-phase-dto';
import { AccessPhaseMapper } from './access-phase/access-phase-mapper';
import { AccessPhaseDTO } from '../../dto/phase/access-phase/access-phase-dto';
import { TransitionPhase } from '../../model/phase/transition-phase';

export class PhaseMapper {
    static fromDTO(dto: AbstractPhaseDTO): TransitionPhase {
        let phase!: TransitionPhase;
        switch (dto.phase_type) {
            case AbstractPhaseDTO.PhaseTypeEnum.TRAINING: {
                phase = TrainingPhaseMapper.fromDTO(dto as TrainingPhaseDTO);
                break;
            }
            case AbstractPhaseDTO.PhaseTypeEnum.INFO: {
                phase = InfoPhaseMapper.fromDTO(dto as InfoPhaseDTO);
                break;
            }
            case AbstractPhaseDTO.PhaseTypeEnum.QUESTIONNAIRE: {
                phase = QuestionnairePhaseMapper.fromDTO(dto as QuestionnairePhaseDTO);
                break;
            }
            case AbstractPhaseDTO.PhaseTypeEnum.ACCESS: {
                phase = AccessPhaseMapper.fromDTO(dto as AccessPhaseDTO);
                break;
            }
        }
        phase.id = dto.id;
        phase.title = dto.title;
        phase.order = dto.order;
        return phase;
    }

    static fromDTOs(dtos: AbstractPhaseDTO[]): TransitionPhase[] {
        return dtos.map((dto) => PhaseMapper.fromDTO(dto)).sort((a, b) => a.order - b.order);
    }
}
