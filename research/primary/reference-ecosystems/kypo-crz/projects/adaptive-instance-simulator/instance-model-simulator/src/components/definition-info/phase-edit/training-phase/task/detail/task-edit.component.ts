import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { Task } from '@crczp/training-model';

@Component({
    selector: 'crczp-task-configuration',
    templateUrl: './task-edit.component.html',
    styleUrls: ['./task-edit.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TaskEditComponent {
    @Input() task: Task;
}
