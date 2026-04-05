import { Component } from '@angular/core';
import { Agenda, AgendaContainer } from '@sentinel/layout';
import { SentinelAuthService, User } from '@sentinel/auth';
import { filter, map, Observable } from 'rxjs';

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.scss'],
})
export class AppComponent {
    title = 'adaptive-instance-simulator';
    agendaContainers$: Observable<AgendaContainer[]>;
    activeUser$: Observable<User>;

    constructor(private auth: SentinelAuthService) {
        this.activeUser$ = this.auth.activeUser$;
        this.agendaContainers$ = this.auth.activeUser$.pipe(
            filter((user) => user !== null && user !== undefined),
            map((user) => this.buildNav(user)),
        );
    }

    buildNav(user: User): AgendaContainer[] {
        const agendas = [];
        if (user.roles.some((role) => role.roleType === 'ROLE_TRAINING_TRAINEE')) {
            agendas.push(
                new AgendaContainer('Tools', [
                    new Agenda('Pre-training', 'home'),
                    new Agenda('Post-training', 'instance-model-simulator'),
                ]),
            );
        }
        return agendas;
    }

    onLogin(): void {
        this.auth.login();
    }

    onLogout(): void {
        this.auth.logout();
    }
}
