import React, {useEffect, useState} from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import type {DeploymentDetailRouteParameters} from 'src/models/routes';
import {useTranslation} from 'react-i18next';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import {
  useAdminDeleteDeploymentMutation,
  useAdminGetDeploymentElementsQuery,
  useAdminGetDeploymentQuery,
  useAdminGetDeploymentScenarioQuery,
  useAdminGetDeploymentScoresQuery,
} from 'src/slices/apiSlice';
import DeploymentDetailsGraph from 'src/components/Scoring/Graph';
import Editor from '@monaco-editor/react';
import {
  AnchorButton,
  Callout,
  Card,
  Divider,
  Elevation,
  H2,
  H4,
  Icon,
  Tooltip,
} from '@blueprintjs/core';
import SideBar from 'src/components/Exercise/SideBar';
import useAdminExerciseStreaming from 'src/hooks/websocket/useAdminExerciseStreaming';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import RoleScoresButtonGroup from 'src/components/Scoring/RoleScoresButtonGroup';
import {
  tryIntoScoringMetadata,
  isVMDeploymentOngoing,
  formatStringToDateTime,
} from 'src/utils';
import InfoTags from 'src/components/Deployment/InfoTags';
import StatusBox from 'src/components/Deployment/Status/StatusBox';

const DeploymentDetail = () => {
  const {t} = useTranslation();
  const navigate = useNavigate();
  const {exerciseId, deploymentId} = useParams<DeploymentDetailRouteParameters>();
  useAdminExerciseStreaming(exerciseId);
  const queryArguments = exerciseId && deploymentId ? {exerciseId, deploymentId} : skipToken;
  const {data: deployment} = useAdminGetDeploymentQuery(queryArguments);
  const {data: scenario} = useAdminGetDeploymentScenarioQuery(queryArguments);
  const {data: scores} = useAdminGetDeploymentScoresQuery(queryArguments);
  const {data: deploymentElements} = useAdminGetDeploymentElementsQuery(queryArguments);
  const [deleteDeployment] = useAdminDeleteDeploymentMutation();

  const [deploymentInProgress, setDeploymentInProgress] = useState(false);
  const [deploymentBeingRemoved, setDeploymentBeingRemoved] = useState(false);

  useEffect(() => {
    const isOngoing = isVMDeploymentOngoing(deploymentElements ?? []);
    setDeploymentInProgress(isOngoing);
  }, [deploymentElements]);

  const handleDeleteDeployment = async () => {
    try {
      setDeploymentBeingRemoved(true);
      const response = await deleteDeployment({
        exerciseId: deployment?.exerciseId ?? '',
        deploymentId: deployment?.id ?? '',
      }).unwrap();

      if (response === deployment?.id) {
        setDeploymentBeingRemoved(false);
        toastSuccess(t('deployments.deleteSuccess', {
          deploymentName: deployment?.name,
        }));
        navigate(`/exercises/${deployment.exerciseId}`);
      }
    } catch {
      setDeploymentBeingRemoved(false);
      toastWarning(t('deployments.deleteFail'));
    }
  };

  if (exerciseId && deploymentId && deployment && scenario) {
    return (
      <SideBar renderMainContent={() => (
        <>
          <div className='flex justify-between overflow-auto'>
            <div className='flex space-x-6 align-middle'>
              <H2>{deployment.name}</H2>
              <InfoTags deploymentElements={deploymentElements ?? []}/>
            </div>
            <Tooltip
              content={deploymentInProgress
                ? t('deployments.beingDeployed') ?? ''
                : (deploymentBeingRemoved
                  ? t('deployments.beingDeleted') ?? ''
                  : '')}
              disabled={!deploymentInProgress && !deploymentBeingRemoved}
            >
              <AnchorButton
                icon='trash'
                intent='danger'
                disabled={deploymentInProgress || deploymentBeingRemoved}
                loading={deploymentBeingRemoved}
                onClick={handleDeleteDeployment}
              >
                {t('common.delete')}
              </AnchorButton>
            </Tooltip>
          </div>
          <div className='pt-2 pb-4 flex justify-center'>
            <div className='flex-col pr-2'>
              <div className='flex'>
                <Icon icon='time' size={22}/>
                <H4 className='font-bold pl-2'>{t('deployments.startTime')}</H4>
              </div>
              <div>
                <p>{formatStringToDateTime(deployment.start)}</p>
              </div>
            </div>
            <Divider/>
            <div className='flex-col pl-2'>
              <div className='flex'>
                <Icon
                  icon='time'
                  size={22}
                  style={{transform: 'rotate(90deg) translateX(-0.3rem) translateY(0.3rem)'}}
                />
                <H4 className='font-bold pl-2'>{t('deployments.endTime')}</H4>
              </div>
              <div>
                <p>{formatStringToDateTime(deployment.end)}</p>
              </div>
            </div>
          </div>
          <div className='pt-8 pb-4'>
            <StatusBox deploymentElements={deploymentElements ?? []}/>
          </div>
          <div className='pt-8 pb-4'>
            <RoleScoresButtonGroup
              exerciseId={exerciseId}
              deploymentId={deploymentId}
              scenario={scenario}
              scores={scores ?? []}
            />
          </div>
          <DeploymentDetailsGraph
            colorsByRole
            scoringData={tryIntoScoringMetadata(scenario)}
            scores={scores ?? []}
          />
          <Card className='h-[60vh] p-0 mb-4' elevation={Elevation.TWO}>
            <Editor
              value={deployment.sdlSchema}
              defaultLanguage='yaml'
              options={{readOnly: true}}
            />
          </Card>
        </>
      )}
      />
    );
  }

  return (
    <Callout title={t('exercises.noDeploymentInfo') ?? ''}/>
  );
};

export default DeploymentDetail;
