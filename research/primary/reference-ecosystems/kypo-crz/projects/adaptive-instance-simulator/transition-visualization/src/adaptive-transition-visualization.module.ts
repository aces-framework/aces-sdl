import { ModuleWithProviders, NgModule, Optional, SkipSelf } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PlayersTransitionsComponent } from './components/training-runs-transitions/training-runs-transitions.component';
import { PlayerTransitionsComponent } from './components/training-runs-transitions/training-run-transitions/training-run-transitions.component';
import { XAxisBottomComponent } from './components/chart-base/chart-axes/x-axis-bottom/x-axis-bottom.component';
import { XAxisTopComponent } from './components/chart-base/chart-axes/x-axis-top/x-axis-top.component';
import { YAxisLeftComponent } from './components/chart-base/chart-axes/y-axis-left/y-axis-left.component';
import { ChartBaseComponent } from './components/chart-base/chart-base.component';
import { ChartAxesComponent } from './components/chart-base/chart-axes/chart-axes.component';
import { ChartGridLinesComponent } from './components/chart-base/chart-grid-lines/chart-grid-lines.component';
import { XAxisGridLinesComponent } from './components/chart-base/chart-grid-lines/x-axis-grid-lines/x-axis-grid-lines.component';
import { YAxisGridLinesComponent } from './components/chart-base/chart-grid-lines/y-axis-grid-lines/y-axis-grid-lines.component';
import { ChartAxesLabelsComponent } from './components/chart-base/chart-axes-labels/chart-axes-labels.component';
import { YAxisLeftLabelComponent } from './components/chart-base/chart-axes-labels/y-axis-left-lable/y-axis-left-label.component';
import { PlayerPathComponent } from './components/training-runs-transitions/training-run-transitions/training-run-path/training-run-path.component';
import { PlayerPathNodesComponent } from './components/training-runs-transitions/training-run-transitions/training-run-path-nodes/training-run-path-nodes.component';
import { PhasesTasksComponent } from './components/phases-tasks/phases-tasks.component';
import { PhaseTasksComponent } from './components/phases-tasks/phase-tasks/phase-tasks.component';
import { InfoTaskPreviewComponent } from './components/task-preview/info-task-preview/info-task-preview.component';
import { TrainingTaskPreviewComponent } from './components/task-preview/training-task-preview/training-task-preview.component';
import { QuestionnaireTaskPreviewComponent } from './components/task-preview/questionnaire-task-preview/questionnaire-task-preview.component';
import { TaskPreviewComponent } from './components/task-preview/task-preview.component';
import { AbstractQuestionComponent } from './components/task-preview/questionnaire-task-preview/abstract-question/abstract-question.component';
import { RatingFormQuestionDetailComponent } from './components/task-preview/questionnaire-task-preview/abstract-question/rating-form-question-detail/rating-form-question-detail.component';
import { MultipleChoiceQuestionDetailComponent } from './components/task-preview/questionnaire-task-preview/abstract-question/multiple-choice-question-detail/multiple-choice-question-detail.component';
import { FreeFormQuestionDetailComponent } from './components/task-preview/questionnaire-task-preview/abstract-question/free-form-question-detail/free-form-question-detail.component';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { MatButtonModule } from '@angular/material/button';
import { ConfigService } from './config/config.service';
import { AccessTaskPreviewComponent } from './components/task-preview/access-task-preview/access-task-preview.component';
import { MarkedOptions, SentinelMarkdownViewModule } from '@sentinel/components/markdown-view';
import { AdaptiveTransitionVisualizationComponent } from './adaptive-transition-visualization.component';
import { AdaptiveTransitionVisualizationWrapperComponent } from './components/adaptive-transition-visualization-wrapper/adaptive-transition-visualization-wrapper.component';
import { AdaptiveTransitionVisualizationPollingService } from './services/adaptive-transition-visualization-polling.service';
import { AdaptiveTransitionVisualizationService } from './services/adaptive-transition-visualization.service';
import { AdaptiveTransitionVisualizationApi } from './api/adaptive-transition-visualization-api.service';
import { AdaptiveTransitionVisualizationConfig } from './config/adaptive-transition-visualization-config';

const markdownParserConfig = {
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
};

@NgModule({
    declarations: [
        AdaptiveTransitionVisualizationComponent,
        AdaptiveTransitionVisualizationWrapperComponent,
        PlayersTransitionsComponent,
        PlayerTransitionsComponent,
        XAxisBottomComponent,
        XAxisTopComponent,
        YAxisLeftComponent,
        ChartBaseComponent,
        ChartAxesComponent,
        ChartGridLinesComponent,
        XAxisGridLinesComponent,
        YAxisGridLinesComponent,
        ChartAxesLabelsComponent,
        YAxisLeftLabelComponent,
        PlayerPathComponent,
        PlayerPathNodesComponent,
        PhasesTasksComponent,
        PhaseTasksComponent,
        TaskPreviewComponent,
        InfoTaskPreviewComponent,
        AccessTaskPreviewComponent,
        TrainingTaskPreviewComponent,
        QuestionnaireTaskPreviewComponent,
        AbstractQuestionComponent,
        RatingFormQuestionDetailComponent,
        MultipleChoiceQuestionDetailComponent,
        FreeFormQuestionDetailComponent,
    ],
    imports: [
        CommonModule,
        SentinelMarkdownViewModule.forRoot(markdownParserConfig),
        MatIconModule,
        MatDividerModule,
        MatButtonModule,
    ],
    exports: [AdaptiveTransitionVisualizationComponent],
    providers: [
        ConfigService,
        AdaptiveTransitionVisualizationPollingService,
        AdaptiveTransitionVisualizationService,
        AdaptiveTransitionVisualizationApi,
    ],
})
export class AdaptiveTransitionVisualizationModule {
    constructor(@Optional() @SkipSelf() parentModule: AdaptiveTransitionVisualizationModule) {
        if (parentModule) {
            throw new Error('2TrainingsHurdlingVizLibModule is already loaded. Import it in the main module only');
        }
    }

    static forRoot(
        config: AdaptiveTransitionVisualizationModule,
    ): ModuleWithProviders<AdaptiveTransitionVisualizationModule> {
        return {
            ngModule: AdaptiveTransitionVisualizationModule,
            providers: [{ provide: AdaptiveTransitionVisualizationConfig, useValue: config }],
        };
    }
}
