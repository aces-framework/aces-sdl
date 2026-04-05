import { Component, EventEmitter } from '@angular/core';
import { MatDialogRef } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { FileUploadProgressService } from '../../service/instance/file-upload-progress.service';

/**
 * Dialog window component of training instance data upload
 */
@Component({
    selector: 'crczp-training-upload-dialog',
    templateUrl: './instance-upload-dialog.component.html',
    styleUrls: ['./instance-upload-dialog.component.css'],
    providers: [FileUploadProgressService],
})
export class InstanceUploadDialogComponent {
    selectedFile: File;
    uploadInProgress$: Observable<boolean>;
    onUpload$ = new EventEmitter<File>();

    constructor(
        public dialogRef: MatDialogRef<InstanceUploadDialogComponent>,
        private uploadProgressService: FileUploadProgressService,
    ) {
        this.uploadInProgress$ = this.uploadProgressService.isInProgress$;
    }

    /**
     * Cancels the upload and closes the dialog window with no result
     */
    cancel(): void {
        this.dialogRef.close();
    }

    /**
     * Emits upload event with selected file
     */
    upload(): void {
        this.onUpload$.emit(this.selectedFile);
    }

    /**
     * Removes selected file
     */
    clearFile(): void {
        this.selectedFile = null;
    }
}
