import { NgModule } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatRadioModule } from '@angular/material/radio';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatDialogModule } from '@angular/material/dialog';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

/**
 * Material components imports for phases detail edit
 */
@NgModule({
    imports: [
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule,
        MatExpansionModule,
        MatTooltipModule,
        MatCheckboxModule,
        MatMenuModule,
        MatDividerModule,
        MatCardModule,
        MatRadioModule,
        MatSelectModule,
        MatTableModule,
        MatSelectModule,
        MatTableModule,
        MatDialogModule,
        MatSlideToggleModule,
    ],
    exports: [
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule,
        MatExpansionModule,
        MatTooltipModule,
        MatCheckboxModule,
        MatMenuModule,
        MatDividerModule,
        MatCardModule,
        MatRadioModule,
        MatSelectModule,
        MatTableModule,
        MatDialogModule,
        MatSlideToggleModule,
    ],
})
export class PhaseEditMaterialModule {}
