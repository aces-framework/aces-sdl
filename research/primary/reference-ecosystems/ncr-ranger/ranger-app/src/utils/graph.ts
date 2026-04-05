import {type ChartData, type ChartOptions} from 'chart.js';
import {Colors} from '@blueprintjs/core';
import {ExerciseRole} from 'src/models/scenario';
import {DateTime} from 'luxon';
import {type Score} from 'src/models/score';
import cloneDeep from 'lodash.clonedeep';
import {sortByProperty} from 'sort-by-property';
import {LINE_DATASET_TEMPLATE} from 'src/constants';
import {defaultColors, roundToDecimalPlaces} from '.';

export const lineColorsByRole: Record<ExerciseRole, string[]> = {
  [ExerciseRole.Blue]: [
    Colors.BLUE1,
    Colors.BLUE2,
    Colors.BLUE3,
    Colors.BLUE4,
    Colors.BLUE5,
  ],
  [ExerciseRole.Green]: [
    Colors.GREEN1,
    Colors.GREEN2,
    Colors.GREEN3,
    Colors.GREEN4,
    Colors.GREEN5,
  ],
  [ExerciseRole.Red]: [
    Colors.RED1,
    Colors.RED2,
    Colors.RED3,
    Colors.RED4,
    Colors.RED5,
  ],
  [ExerciseRole.White]: [
    Colors.GRAY1,
    Colors.GRAY2,
    Colors.GRAY3,
    Colors.GRAY4,
    Colors.GRAY5,
  ],
};

export const getLineChartOptions = (
  {minLimit, maxLimit, chartTitle, xAxisTitle, yAxisTitle}: {
    minLimit: number | undefined;
    maxLimit: number | undefined;
    chartTitle: string;
    xAxisTitle: string;
    yAxisTitle: string;}) => {
  const minZoomRangeMillis = 60 * 1000;
  const options: ChartOptions<'line'> = {
    showLine: true,
    animation: false,
    parsing: false,
    interaction: {
      mode: 'point',
      axis: 'x',
      intersect: false,
    },
    indexAxis: 'x',
    plugins: {
      tooltip: {
        displayColors: false,
      },

      decimation: {
        enabled: true,
        algorithm: 'lttb',
        threshold: 100,
        samples: 100,
      },

      title: {
        display: true,
        text: chartTitle,
      },
      zoom: {
        pan: {
          enabled: true,
          mode: 'x',
        },
        limits: {
          x: {
            minRange: minZoomRangeMillis,
            min: minLimit,
            max: maxLimit,
          },
          y: {
            min: 'original',
            max: 'original',
          },
        },
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.2,
          },
          pinch: {
            enabled: true,
          },
          mode: 'x',
        },
      },
    },
    responsive: true,
    scales: {
      y: {
        title: {
          display: true,
          text: yAxisTitle,
        },
        min: 0,
      },
      x: {
        title: {
          display: true,
          text: xAxisTitle,
        },
        min: minLimit,
        max: maxLimit,
        ticks: {
          source: 'auto',
        },
        type: 'time',
        time: {
          displayFormats: {
            hour: 'HH:mm',
            minute: 'HH:mm',
            second: 'HH:mm:ss',
          },
        },
      },
    },
  };
  return options;
};

export const getLineColorByMetricReference
= (metricReference: string, metricReferencesByRole: Record<ExerciseRole, Set<string>>) => {
  const roles = Object.keys(metricReferencesByRole) as ExerciseRole[];
  const metricRole = roles.find(role => metricReferencesByRole[role].has(metricReference));

  return metricRole ? lineColorsByRole[metricRole] ?? defaultColors : defaultColors;
};

export const scoreIntoGraphPoint = (score: Score) => ({
  x: DateTime.fromISO(score.timestamp, {zone: 'utc'}).toMillis(),
  y: roundToDecimalPlaces(score.value),
});

export function scoresIntoGraphData(
  scoresByMetrics: Record<string, Score[]>,
  metricReferencesByRole: Record<ExerciseRole, Set<string>>,
  colorsByRole: boolean | undefined,
) {
  const graphData: ChartData<'line'> = {
    datasets: [],
  };

  for (const metricLineLabel in scoresByMetrics) {
    if (scoresByMetrics[metricLineLabel]) {
      const baseDataset = cloneDeep(LINE_DATASET_TEMPLATE);
      baseDataset.label = metricLineLabel;
      if (colorsByRole) {
        const metricName = scoresByMetrics[metricLineLabel][0].metricName
        ?? scoresByMetrics[metricLineLabel][0].metricKey;
        const lineColor = getLineColorByMetricReference(metricName, metricReferencesByRole);
        baseDataset.borderColor = lineColor;
        baseDataset.backgroundColor = lineColor;
      }

      for (const score of scoresByMetrics[metricLineLabel]
        .sort(sortByProperty('timestamp', 'asc'))
      ) {
        const graphPoint = scoreIntoGraphPoint(score);
        (baseDataset.data).push(graphPoint);
      }

      graphData.datasets.push(baseDataset);
    }
  }

  return graphData;
}
