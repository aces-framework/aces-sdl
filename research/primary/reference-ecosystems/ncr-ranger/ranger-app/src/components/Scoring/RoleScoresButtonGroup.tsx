import React from 'react';
import {useTranslation} from 'react-i18next';
import {ExerciseRoleOrder, type Scenario} from 'src/models/scenario';
import {
  calculateTotalScoreForRole,
  flattenEntities,
  getRoleColor,
  getUniqueRoles,
  roundToDecimalPlaces,
} from 'src/utils';
import {ButtonGroup, Button, Icon} from '@blueprintjs/core';
import {useNavigate} from 'react-router-dom';
import {type Score} from 'src/models/score';

const RoleScoresButtonGroup = (
  {exerciseId, deploymentId, scenario, scores}:
  {
    exerciseId: string;
    deploymentId: string;
    scenario: Scenario;
    scores: Score[];
  }) => {
  const {t} = useTranslation();
  const entities = scenario?.entities;
  const navigate = useNavigate();

  if (entities) {
    const flattenedEntities = flattenEntities(entities);
    const roles = getUniqueRoles(flattenedEntities);
    roles.sort((a, b) => ExerciseRoleOrder[a] - ExerciseRoleOrder[b]);

    return (
      <div className='flex flex-col mt-2 text-center'>
        <ButtonGroup fill>
          {roles.map(role => {
            const score = calculateTotalScoreForRole(
              {scenario, scores, role});
            const roundedScore = roundToDecimalPlaces(score);
            return (
              <Button
                key={role}
                style={{backgroundColor: getRoleColor(role)}}
                className='rounded-full mb-4 hover:scale-105 transition-all'
                rightIcon={
                  <Icon
                    icon='plus'
                    color='white'/>
                }
                alignText='center'
                onClick={() => {
                  navigate(`/exercises/${exerciseId}/deployments/${deploymentId}/scores/${role}`);
                }}
              >
                <span
                  className='font-bold text-white '
                >
                  {role} {`${t('common.team')}: ${roundedScore} ${t('common.points')}`}
                </span>
              </Button>
            );
          })}
        </ButtonGroup>
      </div>
    );
  }

  return null;
};

export default RoleScoresButtonGroup;
