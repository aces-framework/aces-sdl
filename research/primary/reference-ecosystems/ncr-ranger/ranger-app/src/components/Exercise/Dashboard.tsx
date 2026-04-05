import type React from 'react';
import {useAdminAddDeploymentMutation} from 'src/slices/apiSlice';
import {useTranslation} from 'react-i18next';
import ExerciseForm from 'src/components/Exercise/Form';
import type {
  Deployment,
  DeploymentForm,
  NewDeployment,
} from 'src/models/deployment';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import AddDialog from 'src/components/Deployment/AddDialog';
import {type Exercise} from 'src/models/exercise';
import {useState} from 'react';
import {Alert, Button} from '@blueprintjs/core';

const DashboardPanel = ({exercise, deployments}:
{exercise: Exercise | undefined;
  deployments: Deployment[] | undefined;
}) => {
  const {t} = useTranslation();
  const [addDeployment, _newDeployment] = useAdminAddDeploymentMutation();
  const [isModified, setIsModified] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const createNewDeployments = (
    deploymentForm: DeploymentForm,
  ): [NewDeployment[], string] | undefined => {
    if (exercise?.sdlSchema && exercise?.id) {
      const count = deploymentForm.count;
      const deployments = [];
      for (let index = 0; index < count; index += 1) {
        deployments.push({
          name: count < 2 ? deploymentForm.name : `${deploymentForm.name}-${index}`,
          sdlSchema: exercise.sdlSchema,
          deploymentGroup: deploymentForm.deploymentGroup,
          groupName: deploymentForm.groupNames[index].groupName,
          start: deploymentForm.start,
          end: deploymentForm.end,
        });
      }

      return [deployments, exercise.id];
    }

    toastWarning(t('deployments.sdlMissing'));
  };

  const createPromises = (
    count: number,
    exerciseId: string,
    deployments: NewDeployment[],
  ) => {
    const promises = [];
    for (let index = 0; index < count; index += 1) {
      promises.push(
        addDeployment({newDeployment: deployments[index], exerciseId}),
      );
    }

    return promises.map(async promise =>
      promise.unwrap()
        .then(newDeployment => {
          toastSuccess(
            t(
              'deployments.addingSuccess',
              {newDeploymentName: newDeployment.name},
            ),
          );
        })
        .catch(() => {
          toastWarning(t('deployments.addingFail'));
        }));
  };

  const addNewDeployment = async (
    deploymentForm: DeploymentForm,
  ) => {
    const deploymentsInfo = createNewDeployments(deploymentForm);
    if (deploymentsInfo) {
      const [deployments, exerciseId] = deploymentsInfo;

      const promises = createPromises(
        deploymentForm.count,
        exerciseId,
        deployments,
      );
      await Promise.all(promises);
    }
  };

  if (exercise && deployments) {
    return (
      <>
        <ExerciseForm
          exercise={exercise}
          onContentChange={isChanged => {
            setIsModified(isChanged);
          }}
        >
          <Button
            large
            intent='success'
            onClick={() => {
              setIsAddDialogOpen(true);
            }}
          >
            {t('deployments.create')}
          </Button>
        </ExerciseForm>
        <Alert
          isOpen={isModified && isAddDialogOpen}
          onConfirm={() => {
            setIsModified(false);
          }}
        >
          <p>{t('exercises.sdlNotSaved')}</p>
        </Alert>
        <AddDialog
          isOpen={!isModified && isAddDialogOpen}
          title={t('deployments.title')}
          deploymentGroup={exercise.deploymentGroup}
          onCancel={() => {
            setIsAddDialogOpen(false);
          }}
          onSubmit={async deployment => {
            await addNewDeployment(deployment);
            setIsAddDialogOpen(false);
          }}
        />
      </>
    );
  }

  return null;
};

export default DashboardPanel;
