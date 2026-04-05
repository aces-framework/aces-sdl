import { CommonModule } from '@angular/common';
import { NgModule } from '@angular/core';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { SentinelControlsComponent } from '@sentinel/components/controls';
import { SentinelFreeFormComponent } from '@sentinel/components/free-form';
import { SentinelMarkdownEditorModule } from '@sentinel/components/markdown-editor';
import { SentinelStepperModule } from '@sentinel/components/stepper';
import { AbstractPhaseEditComponent } from './abstract-phase-edit.component';
import { InfoPhaseEditComponent } from './info-phase/info-phase-edit.component';
import { PhaseEditMaterialModule } from './phase-edit-material.module';
import { TaskEditComponent } from './training-phase/task/detail/task-edit.component';
import { TrainingPhaseEditComponent } from './training-phase/training-phase-edit.component';
import { TasksOverviewComponent } from './training-phase/task/overview/tasks-overview.component';
import { TaskStepperComponent } from './training-phase/task/stepper/task-stepper.component';
import { QuestionnairePhaseEditComponent } from './questionnaire/questionnaire-phase-edit.component';
import { QuestionEditComponent } from './questionnaire/question/detail/question-edit.component';
import { QuestionsOverviewComponent } from './questionnaire/question/overview/questions-overview.component';
import { FreeFormQuestionEditComponent } from './questionnaire/question/free-form-question/free-form-question-edit.component';
import { MultipleChoiceQuestionEditComponent } from './questionnaire/question/multiple-choice-question/multiple-choice-question-edit.component';
import { RatingFormQuestionEditComponent } from './questionnaire/question/rating-form-question/rating-form-question-edit.component';
import { MarkedOptions } from '@sentinel/components/markdown-view';

const markdownConfig = {
    markdownParser: {
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
    },
    markdownEditor: {
        fileUploadRestUrl: '',
    },
};

/**
 * Module containing components and providers related to phases edit/detail
 */
@NgModule({
    imports: [
        CommonModule,
        FormsModule,
        SentinelFreeFormComponent,
        SentinelMarkdownEditorModule.forRoot(markdownConfig),
        SentinelStepperModule,
        PhaseEditMaterialModule,
        ReactiveFormsModule,
        SentinelControlsComponent,
    ],
    exports: [AbstractPhaseEditComponent],
    declarations: [
        InfoPhaseEditComponent,
        AbstractPhaseEditComponent,
        TaskEditComponent,
        TrainingPhaseEditComponent,
        TasksOverviewComponent,
        TaskStepperComponent,
        QuestionnairePhaseEditComponent,
        QuestionEditComponent,
        QuestionsOverviewComponent,
        FreeFormQuestionEditComponent,
        MultipleChoiceQuestionEditComponent,
        RatingFormQuestionEditComponent,
    ],
})
export class PhaseEditComponentsModule {}
