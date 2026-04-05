import { NgModule } from '@angular/core';
import { ModelSimulatorPageComponent } from './model-simulator-page.component';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
    {
        path: '',
        component: ModelSimulatorPageComponent,
    },
];

@NgModule({
    imports: [RouterModule.forChild(routes)],
    exports: [RouterModule],
})
export class ModelSimulatorPageRoutingModule {}
