import {sortByProperty} from 'sort-by-property';
import {type Deployment} from 'src/models/deployment';
import {
  ExerciseRole,
  ExerciseRoleOrder,
  type Scenario,
} from 'src/models/scenario';
import {type DeploymentScore} from 'src/models/score';
import {flattenEntities, getTloKeysByRole, getUniqueRoles} from '.';

export function getExerciseRoleFromString(role: string): ExerciseRole | undefined {
  const roles = Object.keys(ExerciseRole) as ExerciseRole[];
  return roles.find(r => r.toLowerCase() === role.toLowerCase());
}

function calculateTotalScore(
  deploymentScores: DeploymentScore[],
  deploymentId: string): number {
  const deploymentScore = deploymentScores.find(ds => ds.deploymentId === deploymentId);
  return deploymentScore
    ? deploymentScore.roleScores.reduce((total, rs) => total + rs.score, 0) : 0;
}

export const sortDeployments = (
  selectedRole: string,
  deployments: Deployment[],
  deploymentScores: DeploymentScore[],
  sortOrder: string) => {
  if (sortOrder.includes('created')) {
    const order = sortOrder === 'createdDesc' ? 'desc' : 'asc';
    return deployments.slice().sort(sortByProperty('createdAt', order));
  }

  if (sortOrder.includes('name')) {
    const order = sortOrder === 'nameDesc' ? 'desc' : 'asc';
    return deployments.slice().sort(sortByProperty('name', order));
  }

  if (sortOrder.includes('score')) {
    const isDescending = sortOrder === 'scoreDesc';

    return deployments.slice().sort((a, b) => {
      let scoreA;
      let scoreB;

      if (selectedRole === 'all' || selectedRole === '') {
        scoreA = calculateTotalScore(deploymentScores, a.id);
        scoreB = calculateTotalScore(deploymentScores, b.id);
      } else {
        const deploymentScoreA = deploymentScores.find(ds => ds.deploymentId === a.id);
        const deploymentScoreB = deploymentScores.find(ds => ds.deploymentId === b.id);

        scoreA = deploymentScoreA?.roleScores.find(rs => rs.role === selectedRole)?.score
          ?? (isDescending ? Number.MIN_SAFE_INTEGER : Number.MAX_SAFE_INTEGER);
        scoreB = deploymentScoreB?.roleScores.find(rs => rs.role === selectedRole)?.score
          ?? (isDescending ? Number.MIN_SAFE_INTEGER : Number.MAX_SAFE_INTEGER);
      }

      return isDescending ? scoreB - scoreA : scoreA - scoreB;
    });
  }

  return deployments;
};

export const getRolesFromScenario = (scenario: Scenario): ExerciseRole[] => {
  if (!scenario.entities) {
    return [];
  }

  const flattenedEntities = flattenEntities(scenario?.entities);
  const fetchedRoles = getUniqueRoles(flattenedEntities);

  const rolesWithTlos: ExerciseRole[] = [];

  for (const role of fetchedRoles) {
    const roleTloNames = getTloKeysByRole(flattenedEntities, role);
    if (roleTloNames.length > 0) {
      rolesWithTlos.push(role);
    }
  }

  rolesWithTlos.sort((a, b) => ExerciseRoleOrder[a] - ExerciseRoleOrder[b]);
  return rolesWithTlos;
};
