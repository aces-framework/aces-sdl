import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { AccessPhaseTask } from '../../../model/phase/access-phase/access-phase-task';

@Component({
    // eslint-disable-next-line @angular-eslint/component-selector
    selector: 'crczp-access-task-preview',
    templateUrl: './access-task-preview.component.html',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccessTaskPreviewComponent {
    @Input() task?: AccessPhaseTask;
    @Input() localEnvironment?: boolean;
}
