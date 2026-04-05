import type React from 'react';
import {useLocation, useNavigate, useParams} from 'react-router-dom';
import type {DeploymentDetailRouteParameters} from 'src/models/routes';
import {
  useParticipantGetDeploymentQuery,
  useParticipantGetExerciseQuery,
  useParticipantGetOwnParticipantsQuery,
} from 'src/slices/apiSlice';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import {useTranslation} from 'react-i18next';
import {
  H2,
  H4,
  Menu,
  MenuDivider,
  MenuItem,
} from '@blueprintjs/core';
import {type ReactNode, useState} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {selectedEntity, setSelectedEntity} from 'src/slices/userSlice';
import EntitySelect from 'src/components/EntitySelect';

export type ParticipantActiveTab =
'Dash' | 'Score' | 'Events' | 'Accounts' | 'User Submissions' | undefined;

const hashToTab = (hash: string): ParticipantActiveTab => {
  switch (hash) {
    case '#dash': {
      return 'Dash';
    }

    case '#events': {
      return 'Events';
    }

    case '#score': {
      return 'Score';
    }

    case '#accounts': {
      return 'Accounts';
    }

    case '#submissions': {
      return 'User Submissions';
    }

    default: {
      return 'Dash';
    }
  }
};

const SideBar = ({renderMainContent}: {
  renderMainContent?: (activeTab: ParticipantActiveTab) => ReactNode | undefined;}) => {
  const {t} = useTranslation();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const {hash} = useLocation();

  const currentEntity = useSelector(selectedEntity);
  const [activeTab, setActiveTab] = useState<ParticipantActiveTab>(hashToTab(hash));
  const {exerciseId, deploymentId}
    = useParams<DeploymentDetailRouteParameters>();

  const {data: exercise} = useParticipantGetExerciseQuery(exerciseId ?? skipToken);
  const deploymentQueryArguments = exerciseId && deploymentId
    ? {exerciseId, deploymentId} : skipToken;
  const {data: deployment} = useParticipantGetDeploymentQuery(deploymentQueryArguments);
  const {data: participants}
  = useParticipantGetOwnParticipantsQuery(exerciseId && deploymentId
    ? {exerciseId, deploymentId} : skipToken);

  if (exercise && deployment) {
    return (

      <div className='flex h-[100%]'>
        <div className='pb-[2rem]'>
          <Menu large className='max-w-[10rem] bp5-elevation-3 h-[100%]'>
            <div className='flex flex-col max-h-[100%] overflow-y-auto'>
              <div className='mt-[2rem] px-[7px]'>
                <H2>{exercise.name}</H2>
                <H4>{deployment.name}</H4>
                <EntitySelect
                  participants={participants ?? []}
                  selectedEntityKey={currentEntity}
                  onChange={(selectedKey: string | undefined) => {
                    dispatch(setSelectedEntity(selectedKey));
                  }}
                />
              </div>
              <MenuDivider/>
              <MenuItem
                active={!deploymentId && activeTab === 'Dash'}
                text={t('participant.exercise.tabs.dash')}
                icon='control'
                onClick={() => {
                  navigate(`/exercises/${exercise.id}/deployments/${deployment.id}#dash`);

                  setActiveTab('Dash');
                }}
              />

              <MenuItem
                active={!deploymentId && activeTab === 'Score'}
                text={t('participant.exercise.tabs.score')}
                icon='chart'
                onClick={() => {
                  navigate(`/exercises/${exercise.id}/deployments/${deployment.id}#score`);

                  setActiveTab('Score');
                }}
              />

              <MenuItem
                active={!deploymentId && activeTab === 'Events'}
                text={t('participant.exercise.tabs.events')}
                icon='timeline-events'
                onClick={() => {
                  navigate(`/exercises/${exercise.id}/deployments/${deployment.id}#events`);

                  setActiveTab('Events');
                }}
              />

              <MenuItem
                active={!deploymentId && activeTab === 'Accounts'}
                text={t('participant.exercise.tabs.accounts')}
                icon='mugshot'
                onClick={() => {
                  navigate(`/exercises/${exercise.id}/deployments/${deployment.id}#accounts`);

                  setActiveTab('Accounts');
                }}
              />

              <MenuItem
                active={!deploymentId && activeTab === 'User Submissions'}
                text={t('participant.exercise.tabs.userSubmissions')}
                icon='shapes'
                onClick={() => {
                  navigate(`/exercises/${exercise.id}/deployments/${deployment.id}#submissions`);

                  setActiveTab('User Submissions');
                }}
              />

            </div>
          </Menu>
        </div>
        <div className='grow m-[2rem] flex justify-center'>
          <div className='max-w-[80rem] w-[60rem]'>
            {renderMainContent?.(activeTab)}
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default SideBar;
