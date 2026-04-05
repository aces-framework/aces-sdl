import type React from 'react';
import {useLocation, useNavigate, useParams} from 'react-router-dom';
import type {DeploymentDetailRouteParameters} from 'src/models/routes';
import {
  useAdminGetDeploymentElementsQuery,
  useAdminGetDeploymentScenarioQuery,
  useAdminGetDeploymentsQuery,
  useAdminGetExerciseQuery,
} from 'src/slices/apiSlice';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import {useTranslation} from 'react-i18next';
import {
  H2,
  H6,
  Icon,
  Intent,
  Menu,
  MenuDivider,
  MenuItem,
  Spinner,
} from '@blueprintjs/core';
import {type ReactNode, useState, useEffect, useRef} from 'react';
import {MENU_HEADER} from '@blueprintjs/core/lib/esm/common/classes';
import {sortByProperty} from 'sort-by-property';
import {ActiveTab} from 'src/models/exercise';
import {Resizable} from 're-resizable';
import {type Deployment} from 'src/models/deployment';
import {getProgressionAndStatus} from 'src/utils/deploymentStatus';

const hashTabs: Record<string, ActiveTab> = {
  '#dash': ActiveTab.Dash,
  '#scores': ActiveTab.Scores,
  '#emails': ActiveTab.Emails,
  '#emaillogs': ActiveTab.EmailLogs,
  '#sdl': ActiveTab.SDL,
  '#accounts': ActiveTab.Accounts,
  '#entities': ActiveTab.EntitySelector,
  '#submissions': ActiveTab.UserSubmissions,
  '#events': ActiveTab.Events,
};

const intentToIcon = (intent: Intent, progressionValue: number) => {
  switch (intent) {
    case 'danger': {
      return <Icon icon='error' intent={intent}/>;
    }

    case 'success': {
      return <Icon icon='tick-circle' intent={intent}/>;
    }

    default: {
      return <Spinner size={16} intent={intent} value={progressionValue}/>;
    }
  }
};

const DeploymentText = ({deployment}: {deployment: Deployment}) => {
  const {data: deploymentElements} = useAdminGetDeploymentElementsQuery({
    exerciseId: deployment.exerciseId,
    deploymentId: deployment.id,
  });
  const {data: scenario} = useAdminGetDeploymentScenarioQuery({
    exerciseId: deployment.exerciseId,
    deploymentId: deployment.id,
  });
  const intentRef = useRef<Intent>(null);
  const [intent, setIntent] = useState<Intent>(Intent.WARNING);
  const progressionRef = useRef<number>(0);
  const [progressionValue, setProgressionValue] = useState<number>(0);

  useEffect(() => {
    if (deploymentElements && scenario) {
      const [progression, intentStatus] = getProgressionAndStatus(deploymentElements, scenario);
      if (intentRef.current !== intentStatus) {
        setIntent(intentStatus);
      }

      if (progressionRef.current !== progression) {
        setProgressionValue(progression);
      }
    }
  }
  , [deploymentElements, scenario]);

  return (
    <div className={deploymentElements ? '' : 'bp5-skeleton'}>
      <div className='flex items-center'>
        {intentToIcon(intent, progressionValue)}
        <h5 className='ml-2 truncate'>{deployment.name}</h5>
      </div>
    </div>
  );
};

const SideBar = ({renderMainContent}: {
  renderMainContent?: (activeTab: ActiveTab) => ReactNode | undefined;}) => {
  const {t} = useTranslation();
  const navigate = useNavigate();
  const {exerciseId, deploymentId}
    = useParams<DeploymentDetailRouteParameters>();

  const {hash} = useLocation();
  const {data: deployments} = useAdminGetDeploymentsQuery(exerciseId ?? skipToken);
  const {data: exercise} = useAdminGetExerciseQuery(exerciseId ?? skipToken);
  const hasDeployments = deployments && deployments.length > 0;
  const [activeTab, setActiveTab] = useState<ActiveTab>(hashTabs[hash] ?? ActiveTab.Dash);
  if (exercise && deployments) {
    const orderedDeployments = deployments.slice().sort(sortByProperty('name', 'asc'));
    return (
      <div className='flex h-[100%]'>
        <div className='pb-[2rem] '>
          <Resizable
            defaultSize={{width: '20%', height: '100%'}}
            minWidth={200}
            maxWidth={300}
          >
            <Menu large className='max-w-[100%] bp5-elevation-3 h-screen '>
              <div className='flex flex-col max-h-[100%]'>
                <div className='mt-[2rem] px-[7px]'>
                  <H2>{exercise.name}</H2>
                </div>
                <MenuDivider/>
                <MenuItem
                  active={!deploymentId && activeTab === ActiveTab.Dash}
                  text={t('exercises.tabs.dashboard')}
                  icon='control'
                  onClick={() => {
                    if (exerciseId) {
                      navigate(`/exercises/${exerciseId}`);
                    }

                    setActiveTab(ActiveTab.Dash);
                  }}
                />
                <MenuItem
                  active={!deploymentId && activeTab === ActiveTab.Banner}
                  text={t('exercises.tabs.banner')}
                  icon='new-text-box'
                  onClick={() => {
                    if (exerciseId) {
                      navigate(`/exercises/${exerciseId}#banner`);
                    }

                    setActiveTab(ActiveTab.Banner);
                  }}
                />
                <MenuItem
                  disabled={!hasDeployments}
                  active={!deploymentId && activeTab === ActiveTab.Scores}
                  text={t('exercises.tabs.scores')}
                  icon='chart'
                  onClick={() => {
                    if (exerciseId) {
                      navigate(`/exercises/${exerciseId}#scores`);
                    }

                    setActiveTab(ActiveTab.Scores);
                  }}
                />
                <MenuItem
                  active={!deploymentId && activeTab === ActiveTab.Emails}
                  text={t('exercises.tabs.emails')}
                  icon='envelope'
                  onClick={() => {
                    if (exerciseId) {
                      navigate(`/exercises/${exerciseId}#emails`);
                    }

                    setActiveTab(ActiveTab.Emails);
                  }}
                />
                <MenuItem
                  active={!deploymentId && activeTab === ActiveTab.EmailLogs}
                  text={t('exercises.tabs.emailLogs')}
                  icon='th-list'
                  onClick={() => {
                    if (exerciseId) {
                      navigate(`/exercises/${exerciseId}#emaillogs`);
                    }

                    setActiveTab(ActiveTab.EmailLogs);
                  }}
                />

                <li className={MENU_HEADER}>
                  <H6>{t('deployments.title')}</H6>
                </li>

                {hasDeployments && (
                  orderedDeployments.map(deployment => (
                    <MenuItem
                      key={deployment.id}
                      popoverProps={{hoverCloseDelay: 200}}
                      active={deploymentId === deployment.id}
                      text={<DeploymentText deployment={deployment}/>}
                      onClick={() => {
                        navigate(
                          `/exercises/${deployment.exerciseId}/deployments/${deployment.id}`);
                      }}
                    >
                      <MenuItem
                        icon='chart'
                        text={t('exercises.tabs.scores')}
                        active={activeTab === ActiveTab.Scores}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#scores`);
                          setActiveTab(ActiveTab.Scores);
                        }}/>
                      <MenuItem
                        icon='text-highlight'
                        text={t('exercises.tabs.sdl')}
                        active={activeTab === ActiveTab.SDL}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#sdl`);
                          setActiveTab(ActiveTab.SDL);
                        }}/>
                      <MenuItem
                        icon='join-table'
                        text={t('exercises.tabs.accounts')}
                        active={activeTab === ActiveTab.Accounts}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#accounts`);
                          setActiveTab(ActiveTab.Accounts);
                        }}/>
                      <MenuItem
                        icon='data-connection'
                        text={t('exercises.tabs.entities')}
                        active={activeTab === ActiveTab.EntitySelector}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#entities`);
                          setActiveTab(ActiveTab.EntitySelector);
                        }}/>
                      <MenuItem
                        icon='manually-entered-data'
                        text={t('exercises.tabs.userSubmissions')}
                        active={activeTab === ActiveTab.UserSubmissions}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#submissions`);
                          setActiveTab(ActiveTab.UserSubmissions);
                        }}/>
                      <MenuItem
                        icon='timeline-events'
                        text={t('exercises.tabs.events')}
                        active={activeTab === ActiveTab.Events}
                        onClick={() => {
                          navigate(
                          // eslint-disable-next-line max-len
                            `/exercises/${deployment.exerciseId}/deployments/${deployment.id}/focus#events`);
                          setActiveTab(ActiveTab.Events);
                        }}/>
                    </MenuItem>
                  ))
                )}
              </div>
            </Menu>
          </Resizable>
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
