import { RouterModule, Routes } from '@angular/router';
import { NgModule } from '@angular/core';
import { InstanceSimulatorPageComponent } from './instance-simulator-page.component';

const routes: Routes = [
    {
        path: '',
        component: InstanceSimulatorPageComponent,
    },
];

@NgModule({
    imports: [RouterModule.forChild(routes)],
    exports: [RouterModule],
})
export class InstanceSimulatorPageRoutingModule {}
