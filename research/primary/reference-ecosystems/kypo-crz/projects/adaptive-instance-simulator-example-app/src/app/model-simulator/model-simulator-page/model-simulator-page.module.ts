import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModelSimulatorPageComponent } from './model-simulator-page.component';
import { ModelSimulatorPageRoutingModule } from './model-simulator-page-routing.module';
import { ModelSimulatorModule } from '@crczp/adaptive-instance-simulator/model-simulator';

@NgModule({
    declarations: [ModelSimulatorPageComponent],
    imports: [CommonModule, ModelSimulatorModule, ModelSimulatorPageRoutingModule],
})
export class ModelSimulatorPageModule {}
