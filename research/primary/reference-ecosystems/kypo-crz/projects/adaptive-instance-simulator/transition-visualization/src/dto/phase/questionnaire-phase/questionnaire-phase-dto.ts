import { AbstractPhaseDTO } from '../abstract-phase-dto';
import { QuestionDTO } from './question-dto';

export interface QuestionnairePhaseDTO extends AbstractPhaseDTO {
    questions: QuestionDTO[];
    questionnaire_type: QuestionnairePhaseDTO.QuestionnaireTypeEnum;
}

// eslint-disable-next-line @typescript-eslint/no-namespace
export namespace QuestionnairePhaseDTO {
    export type QuestionnaireTypeEnum = 'ADAPTIVE' | 'GENERAL';
    export const QuestionnaireTypeEnum = {
        ADAPTIVE: 'ADAPTIVE' as QuestionnaireTypeEnum,
        GENERAL: 'GENERAL' as QuestionnaireTypeEnum,
    };
}
