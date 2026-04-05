import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PerformanceComponent } from './performance.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { PerformanceSimulatorMaterialModule } from './performance-simulator-material.module';

@NgModule({
    declarations: [PerformanceComponent],
    exports: [PerformanceComponent],
    imports: [CommonModule, FormsModule, ReactiveFormsModule, PerformanceSimulatorMaterialModule],
})
export class PerformanceSimulatorModule {}
