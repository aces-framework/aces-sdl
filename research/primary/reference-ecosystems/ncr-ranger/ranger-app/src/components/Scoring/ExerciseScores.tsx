import type React from 'react';
import PageHolder from 'src/components/PageHolder';
import {useTranslation} from 'react-i18next';
import type {Deployment} from 'src/models/deployment';
import {Callout, H4} from '@blueprintjs/core';
import {useNavigate} from 'react-router-dom';
import ScoreTagGroup from 'src/components/Scoring/ScoreTagGroup';
import {useCallback, useEffect, useState} from 'react';
import {sortDeployments} from 'src/utils/score';
import {type DeploymentScore, type RoleScore} from 'src/models/score';
import DeploymentRoleSelect from './DeploymentRoleSelect';
import SortOrderSelect from './SortOrderSelect';

const ScoresPanel = ({deployments}:
{
  deployments: Deployment[] | undefined;
}) => {
  const {t} = useTranslation();
  const navigate = useNavigate();
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [deploymentScores, setDeploymentScores] = useState<DeploymentScore[]>([]);
  const [sortedDeployments, setSortedDeployments] = useState<Deployment[]>([]);
  const [sortOrder, setSortOrder] = useState<string>('');

  const handleScoresChange = useCallback((deploymentId: string, roleScores: RoleScore[]) => {
    setDeploymentScores(previousScores => {
      const existingScore = previousScores.find(score => score.deploymentId === deploymentId);

      if (existingScore) {
        return previousScores.map(score =>
          score.deploymentId === deploymentId ? {...score, roleScores} : score,
        );
      }

      return [...previousScores, {deploymentId, roleScores}];
    });
  }, []);

  const handleClick = (deploymentId: string) => {
    navigate(`deployments/${deploymentId}`);
  };

  const handleRoleChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedRole(event.target.value);
  }, []);

  const handleSortOrderChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    setSortOrder(event.target.value);
  }, []);

  useEffect(() => {
    if (deployments && sortedDeployments.length === 0) {
      setSortedDeployments(sortDeployments(
        selectedRole, deployments, deploymentScores, sortOrder));
    }
  }, [selectedRole, deployments, deploymentScores, sortOrder, sortedDeployments]);

  useEffect(() => {
    if (deployments && deploymentScores) {
      setSortedDeployments(sortDeployments(
        selectedRole, deployments, deploymentScores, sortOrder));
    }
  }, [selectedRole, deployments, deploymentScores, sortOrder]);

  if (sortedDeployments && sortedDeployments.length > 0) {
    return (
      <PageHolder>
        <div className='flex justify-end space-x-2 mb-2'>
          <DeploymentRoleSelect
            selectedRole={selectedRole}
            handleRoleChange={handleRoleChange}
          />
          <SortOrderSelect
            sortOrder={sortOrder}
            handleSortOrderChange={handleSortOrderChange}
          />
        </div>
        <div className='flex flex-col'>
          <table className='
              bp5-html-table
              bp5-html-table-striped
              bp5-interactive'
          >
            <tbody>
              {sortedDeployments.map(deployment => (
                <tr
                  key={deployment.id}
                  onClick={() => {
                    handleClick(deployment.id);
                  }}
                >
                  <td className='flex flex-row justify-between'>
                    <H4 className='mb-0'>{deployment.name}</H4>
                    <ScoreTagGroup
                      exerciseId={deployment.exerciseId}
                      deploymentId={deployment.id}
                      selectedRole={selectedRole}
                      onScoresChange={(roleScores: RoleScore[]) => {
                        handleScoresChange(deployment.id, roleScores);
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageHolder>
    );
  }

  return (
    <Callout title={t('exercises.noDeployments') ?? ''}/>
  );
};

export default ScoresPanel;
