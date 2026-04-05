import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PathwaySimulatorComponent } from './pathway-simulator.component';
import { AdaptiveTransitionVisualizationModule } from '@crczp/adaptive-instance-simulator/transition-visualization';

@NgModule({
    declarations: [PathwaySimulatorComponent],
    imports: [CommonModule, AdaptiveTransitionVisualizationModule.forRoot(null)],
    exports: [PathwaySimulatorComponent],
})
export class PathwaySimulatorModule {}
