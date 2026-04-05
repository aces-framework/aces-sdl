import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { InfoPhase } from '@crczp/training-model';

/**
 * Component for view of existing Info Phase
 */
@Component({
    selector: 'crczp-info-phase-configuration',
    templateUrl: './info-phase-edit.component.html',
    styleUrls: ['./info-phase-edit.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InfoPhaseEditComponent {
    @Input() phase: InfoPhase;
}
