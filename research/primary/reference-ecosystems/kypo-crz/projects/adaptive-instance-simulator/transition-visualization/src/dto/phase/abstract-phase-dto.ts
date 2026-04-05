export interface AbstractPhaseDTO {
    id: number;
    title: string;
    order: number;
    phase_type: AbstractPhaseDTO.PhaseTypeEnum;
}

// eslint-disable-next-line @typescript-eslint/no-namespace
export namespace AbstractPhaseDTO {
    export type PhaseTypeEnum = 'INFO' | 'TASK' | 'TRAINING' | 'QUESTIONNAIRE' | 'ACCESS';
    export const PhaseTypeEnum = {
        INFO: 'INFO' as PhaseTypeEnum,
        TASK: 'TASK' as PhaseTypeEnum,
        TRAINING: 'TRAINING' as PhaseTypeEnum,
        QUESTIONNAIRE: 'QUESTIONNAIRE' as PhaseTypeEnum,
        ACCESS: 'ACCESS' as PhaseTypeEnum,
    };
}
