import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InstanceSimulatorPageComponent } from './instance-simulator-page.component';
import { InstanceSimulatorPageRoutingModule } from './instance-simulator-page-routing.module';
import { InstanceModelSimulatorModule } from '@crczp/adaptive-instance-simulator/instance-model-simulator';
import { environment } from '../../../environments/environment';
import { MarkedOptions, SentinelMarkdownViewModule } from '@sentinel/components/markdown-view';

const markdownParserConfig = {
    markedOptions: {
        provide: MarkedOptions,
        useValue: {
            gfm: true,
            tables: true,
            breaks: false,
            pedantic: false,
            smartLists: true,
            smartypants: false,
        },
    },
};

@NgModule({
    declarations: [InstanceSimulatorPageComponent],
    imports: [
        CommonModule,
        SentinelMarkdownViewModule.forRoot(markdownParserConfig),
        InstanceSimulatorPageRoutingModule,
        InstanceModelSimulatorModule.forRoot(environment.modelSimulatorConfig),
    ],
})
export class InstanceSimulatorPageModule {}
