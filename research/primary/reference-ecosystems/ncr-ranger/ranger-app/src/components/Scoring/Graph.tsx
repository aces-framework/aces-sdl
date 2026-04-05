import React, {useMemo} from 'react';
import {
  Decimation,
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  TimeScale,
} from 'chart.js';
import {Line} from 'react-chartjs-2';
import zoomPlugin from 'chartjs-plugin-zoom';
import {type Score} from 'src/models/score';
import {
  getMetricReferencesByRole,
  groupByMetricNameAndVmName,
} from 'src/utils';
// eslint-disable-next-line import/no-unassigned-import
import 'chartjs-adapter-luxon';
import {useTranslation} from 'react-i18next';
import {getLineChartOptions, scoresIntoGraphData} from 'src/utils/graph';
import {type ScoringMetadata} from 'src/models/scenario';
import {Callout} from '@blueprintjs/core';

ChartJS.register(
  CategoryScale,
  TimeScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  Decimation,
  zoomPlugin,
);

const DeploymentDetailsGraph = (
  {scoringData, scores, colorsByRole}:
  {
    scoringData: ScoringMetadata | undefined;
    scores: Score[] | undefined;
    colorsByRole?: boolean;
  }) => {
  const {t} = useTranslation();
  const xAxisTitle = t('chart.scoring.xAxisTitle');
  const yAxisTitle = t('chart.scoring.yAxisTitle');
  const chartTitle = t('chart.scoring.title');
  const minLimit = Date.parse(scoringData?.startTime ?? '');
  const maxLimit = Date.parse(scoringData?.endTime ?? '');

  const options = useMemo(() => getLineChartOptions({
    minLimit,
    maxLimit,
    chartTitle,
    xAxisTitle,
    yAxisTitle},
  ), [chartTitle, xAxisTitle, yAxisTitle, minLimit, maxLimit]);

  if (scoringData && scores && scores.length > 0) {
    const metricReferencesByRole = getMetricReferencesByRole(scoringData);
    const groupedScores = groupByMetricNameAndVmName(scores);

    return (
      <Line
        data={scoresIntoGraphData(groupedScores, metricReferencesByRole, colorsByRole)}
        options={options}/>
    );
  }

  return (
    <Callout title={t('chart.scoring.noScoreData') ?? ''}/>
  );
};

export default DeploymentDetailsGraph;
