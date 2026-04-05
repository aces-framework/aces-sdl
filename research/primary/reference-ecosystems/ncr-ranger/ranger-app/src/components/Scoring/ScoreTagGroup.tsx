import React, {useCallback, useEffect, useRef, useState} from 'react';
import {type ExerciseRole} from 'src/models/scenario';
import {type RoleScore} from 'src/models/score';
import {useAdminGetDeploymentScenarioQuery} from 'src/slices/apiSlice';
import {getExerciseRoleFromString, getRolesFromScenario} from 'src/utils/score';
import {skipToken} from '@reduxjs/toolkit/dist/query';
import ScoreTag from './ScoreTag';

const ScoreTagGroup = ({exerciseId, deploymentId, selectedRole, onScoresChange}:
{exerciseId: string;
  deploymentId: string;
  selectedRole: string;
  onScoresChange?: (roleScores: RoleScore[]) => void;
}) => {
  const queryArguments = exerciseId && deploymentId ? {exerciseId, deploymentId} : skipToken;
  const {data: scenario} = useAdminGetDeploymentScenarioQuery(queryArguments);
  const [roleScores, setRoleScores] = useState<RoleScore[]>([]);
  const [roles, setRoles] = useState<ExerciseRole[]>([]);
  const [sortedRoles, setSortedRoles] = useState<ExerciseRole[]>(roles);
  const previousRoleScoresRef = useRef<RoleScore[]>([]);

  useEffect(() => {
    if (scenario) {
      const scenarioRoles = getRolesFromScenario(scenario);
      setRoles(scenarioRoles);
    }
  }
  , [scenario]);

  useEffect(() => {
    if (roles && roles.length > 0) {
      if (selectedRole === 'all' || selectedRole === '') {
        setSortedRoles(roles);
      } else {
        const selectedExerciseRole = getExerciseRoleFromString(selectedRole);
        setSortedRoles(roles.filter(role => role === selectedExerciseRole));
      }
    }
  }
  , [selectedRole, roles]);

  useEffect(() => {
    if (previousRoleScoresRef.current !== roleScores) {
      onScoresChange?.(roleScores);
      previousRoleScoresRef.current = roleScores;
    }
  }, [roleScores, onScoresChange]);

  const handleRoleScoreChange = useCallback((role: ExerciseRole, score: number) => {
    setRoleScores(previousScores => {
      const existingScore = previousScores.find(roleScore => roleScore.role === role);

      if (existingScore) {
        return previousScores.map(roleScore =>
          roleScore.role === role ? {...roleScore, score} : roleScore,
        );
      }

      return [...previousScores, {role, score}];
    });
  }, []);

  if (sortedRoles) {
    return (
      <div className='flex m-1 mt-auto mb-auto'>
        {sortedRoles.map((role: ExerciseRole) => (
          <div key={role} className='flex mr-1'>
            <ScoreTag
              key={role}
              exerciseId={exerciseId}
              deploymentId={deploymentId}
              scenario={scenario}
              role={role}
              onTagScoreChange={score => {
                handleRoleScoreChange(role, score);
              }}
            />
          </div>
        ),
        )}
      </div>
    );
  }

  return null;
};

export default ScoreTagGroup;
