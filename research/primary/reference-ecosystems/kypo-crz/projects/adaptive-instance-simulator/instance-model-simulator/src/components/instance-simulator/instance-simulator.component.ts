import { ChangeDetectionStrategy, Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { SankeyData } from '../../model/sankey/sankey-data';

@Component({
    selector: 'crczp-adaptive-instance-simulator-instance-simulator',
    templateUrl: './instance-simulator.component.html',
    styleUrls: ['./instance-simulator.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InstanceSimulatorComponent implements OnChanges {
    @Input() simulatorData: SankeyData;

    ngOnChanges(changes: SimpleChanges): void {
        if ('simulatorData' in changes && !changes['simulatorData'].isFirstChange()) {
            this.simulatorData = { ...this.simulatorData };
        }
    }
}
