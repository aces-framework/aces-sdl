import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { catchError, map, Observable, throwError } from 'rxjs';
import { SankeyDataMapper } from '../model/sankey/mapper/sankey-data-mapper';
import { SankeyDataDTO } from '../model/sankey/dto/sankey-data-dto';
import { SankeyData } from '../model/sankey/sankey-data';
import { ModelSimulatorConfig } from '@crczp/adaptive-instance-simulator/internal';

@Injectable()
/**
 * Fetches the data from the REST API.
 */
export class SankeyDataService {
    constructor(
        private http: HttpClient,
        private config: ModelSimulatorConfig,
    ) {}

    public getAllData(instanceId: number): Observable<SankeyData> {
        return this.http
            .get<SankeyDataDTO>(
                this.config.adaptiveBasePath + 'visualizations' + '/training-instances/' + instanceId + '/sankey',
            )
            .pipe(
                map((data) => SankeyDataMapper.fromDTOs(data)),
                catchError((error) => {
                    return throwError('Could not connect to API to obtain data: ' + error.message);
                }),
            );
    }
}
