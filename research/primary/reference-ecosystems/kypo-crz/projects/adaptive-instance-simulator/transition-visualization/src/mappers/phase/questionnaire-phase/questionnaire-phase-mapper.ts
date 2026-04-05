import { QuestionnairePhase } from '../../../model/phase/questionnaire-phase/questionnaire-phase';
import { QuestionnairePhaseDTO } from '../../../dto/phase/questionnaire-phase/questionnaire-phase-dto';
import { AbstractPhaseTypeEnum } from '../../../model/enums/abstract-phase-type.enum';
import { QuestionnaireTypeEnum } from '../../../model/enums/questionnaire-type.enum';
import { QuestionnairePhaseTaskMapper } from './questionnaire-phase-task-mapper';

export class QuestionnairePhaseMapper {
    static fromDTO(dto: QuestionnairePhaseDTO): QuestionnairePhase {
        const result = new QuestionnairePhase();
        result.type = AbstractPhaseTypeEnum.Questionnaire;
        switch (dto.questionnaire_type) {
            case 'ADAPTIVE': {
                result.questionnaireType = QuestionnaireTypeEnum.Adaptive;
                break;
            }
            case 'GENERAL': {
                result.questionnaireType = QuestionnaireTypeEnum.General;
                break;
            }
        }

        result.tasks = [QuestionnairePhaseTaskMapper.fromDTO(dto)];

        return result;
    }
}
