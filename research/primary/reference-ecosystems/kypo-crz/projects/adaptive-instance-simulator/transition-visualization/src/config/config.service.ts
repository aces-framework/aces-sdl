import { Injectable } from '@angular/core';
import { AdaptiveTransitionVisualizationConfig } from './adaptive-transition-visualization-config';

@Injectable()
export class ConfigService {
    private readonly _config: AdaptiveTransitionVisualizationConfig;

    get config(): AdaptiveTransitionVisualizationConfig {
        return this._config;
    }

    constructor(config: AdaptiveTransitionVisualizationConfig) {
        this._config = config;
    }
}
