import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { SentinelAuthProviderListComponent } from '@sentinel/auth/components';
import { SentinelAuthGuardWithLogin, SentinelNegativeAuthGuard } from '@sentinel/auth/guards';

const routes: Routes = [
    {
        path: 'home',
        loadChildren: () =>
            import('./model-simulator/model-simulator-page/model-simulator-page.module').then(
                (m) => m.ModelSimulatorPageModule,
            ),
        canActivate: [SentinelAuthGuardWithLogin],
    },
    {
        path: 'instance-model-simulator',
        loadChildren: () =>
            import('./model-simulator/instance-simulator-page/instance-simulator-page.module').then(
                (m) => m.InstanceSimulatorPageModule,
            ),
        canActivate: [SentinelAuthGuardWithLogin],
    },
    {
        path: '',
        redirectTo: 'home',
        pathMatch: 'full',
    },
    {
        path: 'login',
        component: SentinelAuthProviderListComponent,
        canActivate: [SentinelNegativeAuthGuard],
    },
    {
        path: '**',
        redirectTo: 'home',
    },
];

@NgModule({
    imports: [RouterModule.forRoot(routes)],
    exports: [RouterModule],
})
export class AppRoutingModule {}
