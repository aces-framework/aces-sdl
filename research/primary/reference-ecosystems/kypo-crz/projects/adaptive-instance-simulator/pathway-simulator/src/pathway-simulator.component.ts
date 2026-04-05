import { Component, Input } from '@angular/core';
import { TransitionVisualizationData } from '@crczp/adaptive-instance-simulator/transition-visualization';

@Component({
    selector: 'crczp-pathway-simulator',
    templateUrl: './pathway-simulator.component.html',
    styleUrls: ['./pathway-simulator.component.css'],
})
export class PathwaySimulatorComponent {
    @Input() transitionData: TransitionVisualizationData;
}
