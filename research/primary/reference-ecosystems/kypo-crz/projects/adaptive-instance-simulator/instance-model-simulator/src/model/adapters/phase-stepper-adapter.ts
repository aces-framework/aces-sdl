import { StepItem, StepStateEnum } from '@sentinel/components/stepper';
import { AbstractPhaseTypeEnum, Phase, QuestionnairePhase, QuestionnaireTypeEnum } from '@crczp/training-model';

export class PhaseStepperAdapter implements StepItem {
    id: number;
    title: string;
    phase: Phase;
    icon: string;
    state: StepStateEnum;
    type: AbstractPhaseTypeEnum;

    constructor(phase: Phase) {
        this.id = phase.id;
        this.title = phase.title;
        this.phase = phase;
        this.state = StepStateEnum.SELECTABLE;
        this.type = phase.type;
        this.icon = this.getPhaseIcon(phase);
    }

    private getPhaseIcon(phase: Phase): string {
        switch (phase.type) {
            case AbstractPhaseTypeEnum.Info:
                return 'info';
            case AbstractPhaseTypeEnum.Training:
                return 'transform';
            case AbstractPhaseTypeEnum.Task:
                return 'videogame_asset';
            case AbstractPhaseTypeEnum.Questionnaire: {
                switch ((phase as QuestionnairePhase).questionnaireType) {
                    case QuestionnaireTypeEnum.General:
                        return 'help';
                    case QuestionnaireTypeEnum.Adaptive:
                        return 'help_center';
                    default:
                        return 'help';
                }
            }
        }
    }
}
