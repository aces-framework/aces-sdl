import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { AbstractTaskTypeEnum } from '../../model/enums/abstract-task-type.enum';
import { TrainingPhaseTask } from '../../model/phase/training-phase/training-phase-task';
import { InfoPhaseTask } from '../../model/phase/info-phase/info-phase-task';
import { Task } from '../../model/phase/task';
import { QuestionnairePhaseTask } from '../../model/phase/questionnaire-phase/questionnaire-phase-task';
import { AccessPhaseTask } from '../../model/phase/access-phase/access-phase-task';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'crczp-task-preview',
    templateUrl: './task-preview.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TaskPreviewComponent {
    @Input() task?: Task;
    @Input() localEnvironment?: boolean;

    AbstractTaskTypeEnum = AbstractTaskTypeEnum;

    taskTypeResolver(task: Task | undefined) {
        switch (true) {
            case task instanceof InfoPhaseTask:
                return AbstractTaskTypeEnum.Info;
            case task instanceof TrainingPhaseTask:
                return AbstractTaskTypeEnum.Training;
            case task instanceof QuestionnairePhaseTask:
                return AbstractTaskTypeEnum.Questionnaire;
            case task instanceof AccessPhaseTask:
                return AbstractTaskTypeEnum.Access;
            default:
                return '';
        }
    }
}
