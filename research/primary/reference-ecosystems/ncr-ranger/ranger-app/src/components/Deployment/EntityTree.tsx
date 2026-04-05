import {
  type TreeNodeInfo,
  Card,
  Elevation,
  H5,
  Tree,
  Button,
} from '@blueprintjs/core';
import React from 'react';
import {
  useAdminDeleteParticipantMutation,
  useAdminGetDeploymentParticipantsQuery,
  useAdminGetDeploymentQuery,
  useAdminGetDeploymentScenarioQuery,
  useAdminGetGroupUsersQuery,
} from 'src/slices/apiSlice';
import {useTranslation} from 'react-i18next';
import {createEntityTree} from 'src/utils';
import {skipToken} from '@reduxjs/toolkit/dist/query';

export const deleteEntityConnectionButton = (
  clickedDelete: (participantId: string) => void,
  participantId?: string,
) => {
  if (!participantId) {
    return null;
  }

  return (
    <Button
      intent='danger'
      className='delete-button'
      onClick={async () => {
        clickedDelete(participantId);
      }}
    >
      Disconnect
    </Button>
  );
};

const EntityTree = ({exerciseId, deploymentId}: {
  exerciseId: string;
  deploymentId: string;
}) => {
  const {t} = useTranslation();
  const {data: scenario} = useAdminGetDeploymentScenarioQuery({exerciseId, deploymentId});
  const {data: deployment} = useAdminGetDeploymentQuery({exerciseId, deploymentId});
  const {data: users} = useAdminGetGroupUsersQuery(deployment?.groupName ?? skipToken);
  const [deleteParticipant] = useAdminDeleteParticipantMutation();
  const {
    data: participants,
  } = useAdminGetDeploymentParticipantsQuery({exerciseId, deploymentId});

  const tree: TreeNodeInfo[] = React.useMemo(() => {
    if (!scenario?.entities) {
      return [];
    }

    const clickedDelete = async (participantId: string) => {
      await deleteParticipant({
        exerciseId,
        deploymentId,
        participantId,
      });
    };

    return createEntityTree(clickedDelete, scenario.entities, participants, users);
  }, [scenario, participants, users, exerciseId, deploymentId, deleteParticipant]);

  return (
    <Card elevation={Elevation.TWO}>
      <H5>{t('deployments.entityTree')}</H5>
      <Tree
        contents={tree}
      />
    </Card>
  );
};

export default EntityTree;

