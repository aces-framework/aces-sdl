import type React from 'react';
import {useParams} from 'react-router-dom';
import type {DeploymentDetailRouteParameters} from 'src/models/routes';
import {
  useAdminGetDeploymentElementsQuery,
  useAdminGetDeploymentQuery,
  useAdminGetDeploymentScenarioQuery,
  useAdminGetDeploymentScoresQuery,
  useAdminGetDeploymentUsersQuery,
  useAdminGetEventsQuery,
} from 'src/slices/apiSlice';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import SideBar from 'src/components/Exercise/SideBar';
import useAdminExerciseStreaming from 'src/hooks/websocket/useAdminExerciseStreaming';
import DeploymentDetailsGraph from 'src/components/Scoring/Graph';
import TloTable from 'src/components/Scoring/TloTable';
import {Editor} from '@monaco-editor/react';
import AccountList from 'src/components/Deployment/AccountList';
import EntityConnector from 'src/components/Deployment/EntityConnector';
import MetricScorer from 'src/components/Scoring/MetricScorer';
import EntityTree from 'src/components/Deployment/EntityTree';
import {ActiveTab} from 'src/models/exercise';
import {tryIntoScoringMetadata} from 'src/utils';
import {H2} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import ManagerEvents from 'src/components/Deployment/Event/EventList';

const DeploymentFocus = () => {
  const {t} = useTranslation();
  const {exerciseId, deploymentId} = useParams<DeploymentDetailRouteParameters>();
  useAdminExerciseStreaming(exerciseId);
  const queryArguments = exerciseId && deploymentId ? {exerciseId, deploymentId} : skipToken;
  const {data: scenario} = useAdminGetDeploymentScenarioQuery(queryArguments);
  const {data: deployment} = useAdminGetDeploymentQuery(queryArguments);
  const {data: scores} = useAdminGetDeploymentScoresQuery(queryArguments);
  const {data: users} = useAdminGetDeploymentUsersQuery(queryArguments);
  const {data: deploymentElements} = useAdminGetDeploymentElementsQuery(queryArguments);
  const {data: deploymentEvents} = useAdminGetEventsQuery(queryArguments);

  if (scenario && exerciseId && deploymentId) {
    return (
      <SideBar renderMainContent={activeTab => (
        <>
          {activeTab === ActiveTab.Scores && (
            <>
              <H2>{t('exercises.tabs.deploymentScores')}</H2>
              <TloTable
                scoringData={tryIntoScoringMetadata(scenario)}
                scores={scores}
                tloMap={scenario?.tlos}
              />
              <div className='mt-[2rem]'>
                <DeploymentDetailsGraph
                  colorsByRole
                  scoringData={tryIntoScoringMetadata(scenario)}
                  scores={scores}
                />
              </div>
            </>
          )}
          {activeTab === ActiveTab.SDL && (
            <div className='h-[80vh]'>
              <H2>{t('exercises.tabs.sdl')}</H2>
              <Editor
                value={deployment?.sdlSchema ?? ''}
                defaultLanguage='yaml'
                options={{readOnly: true}}
              />
            </div>
          )}
          {activeTab === ActiveTab.Accounts && (
            <div>
              <H2>{t('exercises.tabs.accounts')}</H2>
              <AccountList
                users={users}
                deploymentElements={deploymentElements}
              />
            </div>
          )}
          {activeTab === ActiveTab.EntitySelector && (
            <>
              <H2>{t('exercises.tabs.entities')}</H2>
              <EntityConnector exerciseId={exerciseId} deploymentId={deploymentId}/>
              <div className='mt-[2rem]'>
                <EntityTree exerciseId={exerciseId} deploymentId={deploymentId}/>
              </div>
            </>
          )}
          {activeTab === ActiveTab.UserSubmissions && (
            <>
              <H2>{t('exercises.tabs.userSubmissions')}</H2>
              <MetricScorer
                exerciseId={exerciseId}
                deploymentId={deploymentId}/>
            </>
          )}
          {activeTab === ActiveTab.Events && (
            <>
              <H2>{t('exercises.tabs.events')}</H2>
              <ManagerEvents
                scenario={scenario}
                deploymentEvents={deploymentEvents}
                deploymentElements={deploymentElements}
              />
            </>
          )}
        </>
      )}/>
    );
  }

  return null;
};

export default DeploymentFocus;
