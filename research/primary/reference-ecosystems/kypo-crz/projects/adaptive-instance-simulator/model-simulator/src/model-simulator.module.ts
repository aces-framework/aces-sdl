import { NgModule } from '@angular/core';
import { ModelSimulatorComponent } from './model-simulator.component';
import { ModelSimulatorService } from './service/model-simulator.service';
import { CommonModule } from '@angular/common';
import { PerformanceSimulatorModule } from '@crczp/adaptive-instance-simulator/performance-simulator';
import { PathwaySimulatorModule } from '@crczp/adaptive-instance-simulator/pathway-simulator';
import { MatDividerModule } from '@angular/material/divider';

@NgModule({
    declarations: [ModelSimulatorComponent],
    providers: [ModelSimulatorService],
    exports: [ModelSimulatorComponent],
    imports: [CommonModule, PerformanceSimulatorModule, PathwaySimulatorModule, MatDividerModule],
})
export class ModelSimulatorModule {}
