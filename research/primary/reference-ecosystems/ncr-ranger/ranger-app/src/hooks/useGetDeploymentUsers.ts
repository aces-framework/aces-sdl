import {useState} from 'react';
import {useSelector} from 'react-redux';
import {type AdUser} from 'src/models/groups';
import {type RootState} from 'src/store';

type DeploymentUsers = Record<string, AdUser[]>;

const useGetDeploymentUsers = () => {
  const [deploymentUsers, setDeploymentUsers] = useState<DeploymentUsers>({});
  const token = useSelector((state: RootState) => state.user.token);
  const fetchDeploymentUsers = async (deploymentId: string, groupName: string) => {
    if (!token) {
      return;
    }

    const response = await fetch(`/api/v1/admin/group/${groupName}/users`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json() as AdUser[];
    setDeploymentUsers(previous => ({
      ...previous,
      [deploymentId]: data,
    }));
  };

  return {
    deploymentUsers,
    fetchDeploymentUsers,
  };
};

export default useGetDeploymentUsers;
