import {type ChartDataset} from 'chart.js';
import {Colors} from '@blueprintjs/core';
import {defaultColors} from 'src/utils';

export const BASE_URL = '/api/v1';
export const LINE_DATASET_TEMPLATE: ChartDataset<'line'> = {
  type: 'line',
  tension: 0.3,
  borderColor: defaultColors,
  backgroundColor: defaultColors,
  pointBackgroundColor: Colors.WHITE,
  pointBorderColor: Colors.GRAY3,
  borderWidth: 1,
  parsing: false,
  fill: false,
  pointRadius: 1.5,
  data: [],
};
export const ARTIFACT_FILETYPE_WHITELIST = 'application/zip, .zip';
