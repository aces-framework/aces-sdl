import type React from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import {type ParticipantExercise} from 'src/models/exercise';
import type {DeploymentDetailRouteParameters} from 'src/models/routes';
import {useParticipantGetDeploymentsQuery} from 'src/slices/apiSlice';
import {H6, MenuItem} from '@blueprintjs/core';

const DeploymentList = ({exercise}: {exercise: ParticipantExercise}) => {
  const navigate = useNavigate();
  const {deploymentId}
    = useParams<DeploymentDetailRouteParameters>();
  const {data: deployments} = useParticipantGetDeploymentsQuery(exercise.id);
  const hasDeployments = deployments && deployments.length > 0;

  return (
    <div className='flex flex-col'>
      <H6 className='px-[7px] pt-[7px] pb-[7px] text-[#5c7080]'>
        {exercise.name}
      </H6>
      { hasDeployments && (deployments.map(deployment => (
        <MenuItem
          key={deployment.id}
          active={deploymentId === deployment.id}
          text={deployment.name}
          icon='cloud-upload'
          onClick={() => {
            navigate(
              `/exercises/${exercise.id}/deployments/${deployment.id}`);
          }}
        />
      )))}
    </div>
  );
};

export default DeploymentList;
