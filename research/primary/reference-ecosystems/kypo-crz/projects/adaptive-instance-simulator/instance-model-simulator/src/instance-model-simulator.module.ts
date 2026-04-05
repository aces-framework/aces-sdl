import { ModuleWithProviders, NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InstanceModelSimulatorComponent } from './instance-model-simulator.component';
import { InstanceModelSimulatorMaterialModule } from './instance-model-simulator-material.module';
import { DefinitionInfoComponent } from './components/definition-info/definition-info.component';
import { InstanceSimulatorComponent } from './components/instance-simulator/instance-simulator.component';
import { SentinelControlsComponent } from '@sentinel/components/controls';
import { InstanceUploadDialogComponent } from './components/instance-upload-dialog/instance-upload-dialog.component';
import { ngfModule } from 'angular-file';
import { SentinelPipesModule } from '@sentinel/common/pipes';
import { ModelSimulatorConfig } from '@crczp/adaptive-instance-simulator/internal';
import { SentinelFreeFormComponent } from '@sentinel/components/free-form';
import { PhaseStepperComponent } from './components/definition-info/stepper/phase-stepper.component';
import { SentinelStepperModule } from '@sentinel/components/stepper';
import { PhaseEditComponentsModule } from './components/definition-info/phase-edit/phase-edit-components.module';
import { InstanceSimulatorService } from './service/instance/instance-simulator.service';
import { InstanceSimulatorApiService } from './service/instance/instance-simulator-api.service';
import { FileUploadProgressService } from './service/instance/file-upload-progress.service';
import { SankeyVisualizationComponent } from './components/sankey-visualization/sankey-visualization.component';
import { SankeyDataService } from './service/sankey-data.service';

@NgModule({
    declarations: [
        InstanceModelSimulatorComponent,
        DefinitionInfoComponent,
        InstanceSimulatorComponent,
        InstanceUploadDialogComponent,
        PhaseStepperComponent,
        SankeyVisualizationComponent,
    ],
    exports: [InstanceModelSimulatorComponent, SankeyVisualizationComponent],
    imports: [
        CommonModule,
        InstanceModelSimulatorMaterialModule,
        SentinelControlsComponent,
        ngfModule,
        SentinelPipesModule,
        PhaseEditComponentsModule,
        SentinelFreeFormComponent,
        SentinelStepperModule,
    ],
    providers: [InstanceSimulatorService, FileUploadProgressService, InstanceSimulatorApiService, SankeyDataService],
})
export class InstanceModelSimulatorModule {
    static forRoot(config: ModelSimulatorConfig): ModuleWithProviders<InstanceModelSimulatorModule> {
        return {
            ngModule: InstanceModelSimulatorModule,
            providers: [
                {
                    provide: ModelSimulatorConfig,
                    useValue: config,
                },
            ],
        };
    }
}
