import { Component } from '@angular/core';

@Component({
    selector: 'app-instance-simulator-page',
    templateUrl: './instance-simulator-page.component.html',
    styleUrls: ['./instance-simulator-page.component.css'],
})
export class InstanceSimulatorPageComponent {
    handleState(event): void {
        console.log(event);
    }
}
