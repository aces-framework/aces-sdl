import React from 'react';
import {useParams} from 'react-router-dom';
import type {DeploymentDetailScoresRouteParameters} from 'src/models/routes';
import {useTranslation} from 'react-i18next';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import {
  useAdminGetDeploymentScenarioQuery,
  useAdminGetDeploymentScoresQuery,
} from 'src/slices/apiSlice';
import useAdminExerciseStreaming from 'src/hooks/websocket/useAdminExerciseStreaming';
import {ExerciseRoleOrder} from 'src/models/scenario';
import {
  flattenEntities,
  getTloKeysByRole,
  getUniqueRoles,
  groupTloMapsByRoles,
  tryIntoScoringMetadata,
} from 'src/utils';
import TloTable from 'src/components/Scoring/TloTable';
import DeploymentDetailsGraph from 'src/components/Scoring/Graph';
import PageHolder from 'src/components/PageHolder';
import SideBar from 'src/components/Exercise/SideBar';
import ScoreTag from 'src/components/Scoring/ScoreTag';
import {Callout} from '@blueprintjs/core';

const ScoreDetail = () => {
  const {t} = useTranslation();
  const {exerciseId, deploymentId, role} = useParams<DeploymentDetailScoresRouteParameters>();
  useAdminExerciseStreaming(exerciseId);
  const queryArguments = exerciseId && deploymentId ? {exerciseId, deploymentId} : skipToken;
  const {data: scenario} = useAdminGetDeploymentScenarioQuery(queryArguments);
  const {data: scores} = useAdminGetDeploymentScoresQuery(queryArguments);
  const scoringData = tryIntoScoringMetadata(scenario);

  if (deploymentId && exerciseId && role && scoringData) {
    const flattenedEntities = flattenEntities(scoringData.entities);
    const tloKeysByRole = getTloKeysByRole(flattenedEntities, role);
    const roles = getUniqueRoles(flattenedEntities)
      .sort((a, b) => ExerciseRoleOrder[a] - ExerciseRoleOrder[b]);
    const tlosByRole = groupTloMapsByRoles(flattenedEntities, scoringData.tlos, roles);
    const metricKeysByRole = new Set(tloKeysByRole.map(tloKey => scoringData.tlos[tloKey])
      .map(tlo => tlo.evaluation)
      .map(evaluationKey => scoringData.evaluations[evaluationKey])
      .flatMap(evaluation => evaluation.metrics));
    const filteredScores = scores?.filter(score => metricKeysByRole.has(score.metricKey));

    return (
      <SideBar renderMainContent={() => (
        <PageHolder>
          <div>
            <div className='flex flex-col mt-6 text-center font-bold'>
              <ScoreTag
                key={role}
                large
                exerciseId={exerciseId}
                deploymentId={deploymentId}
                scenario={scenario}
                role={role}
              />
            </div>
            <DeploymentDetailsGraph
              scoringData={scoringData}
              scores={filteredScores}
            />
            <TloTable
              scoringData={scoringData}
              scores={filteredScores}
              tloMap={tlosByRole[role]}
            />
          </div>
        </PageHolder>
      )}
      />
    );
  }

  return (
    <Callout title={t('exercises.noDeploymentInfo') ?? ''}/>
  );
};

export default ScoreDetail;
