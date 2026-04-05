import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { TransitionVisualizationData } from '../model/transition-visualization-data';
import { HttpErrorResponse } from '@angular/common/http';
import { tap } from 'rxjs/operators';
import { AdaptiveTransitionVisualizationApi } from '../api/adaptive-transition-visualization-api.service';

@Injectable({
    providedIn: 'root',
})
export class AdaptiveTransitionVisualizationService {
    /**
     * True if server returned error response on the latest request, false otherwise
     * Change internally in extending service. Client should subscribe to the observable
     */
    private hasErrorSubject$: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(false);

    /**
     * True if server returned error response on the latest request, false otherwise
     * @contract must be updated every time new data are received
     */
    hasError$: Observable<boolean> = this.hasErrorSubject$.asObservable();

    /**
     * True if response to the latest request was not yet received
     * Change internally in extending service. Client should subscribe to the observable
     */
    private isLoadingSubject$: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(true);

    /**
     * True if response to the latest request was not yet received
     * @contract must be updated every time new data are received
     */
    isLoading$: Observable<boolean> = this.isLoadingSubject$.asObservable();

    private visualizationDataSubject$: BehaviorSubject<TransitionVisualizationData> =
        new BehaviorSubject<TransitionVisualizationData>(null as unknown as TransitionVisualizationData);

    visualizationData$!: Observable<TransitionVisualizationData>;

    constructor(private visualizationApi: AdaptiveTransitionVisualizationApi) {
        this.visualizationData$ = this.visualizationDataSubject$.asObservable();
    }

    /**
     * Gets all visualization data and updates related observables or handles an error
     * @param trainingInstanceId id of training instance
     */
    getAllForTrainingInstance(trainingInstanceId: number): Observable<TransitionVisualizationData> {
        return this.callForTrainingInstance(trainingInstanceId).pipe(
            tap(
                (data) => {
                    this.isLoadingSubject$.next(false);
                    this.visualizationDataSubject$.next(data);
                },
                (err) => this.onGetAllError(err),
            ),
        );
    }

    /**
     * Gets all stages and updates related observables or handles an error
     * @param trainingRunId id of training run
     */
    getAllForTrainingRun(trainingRunId: number): Observable<TransitionVisualizationData> {
        return this.callForTrainingRun(trainingRunId).pipe(
            tap(
                (data) => {
                    this.isLoadingSubject$.next(false);
                    this.visualizationDataSubject$.next(data);
                },
                (err) => this.onGetAllError(err),
            ),
        );
    }

    protected callForTrainingInstance(trainingRunId: number): Observable<TransitionVisualizationData> {
        return this.visualizationApi.getDataForTrainingInstance(trainingRunId);
    }

    protected callForTrainingRun(trainingRund: number): Observable<TransitionVisualizationData> {
        return this.visualizationApi.getDataForTrainingRun(trainingRund);
    }

    protected onGetAllError(err: HttpErrorResponse): void {
        this.hasErrorSubject$.next(true);
    }
}
