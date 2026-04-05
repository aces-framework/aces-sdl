import type React from 'react';
import {useEffect, useState} from 'react';
import {AnchorButton, Card, H2, Tooltip} from '@blueprintjs/core';
import {useNavigate} from 'react-router-dom';
import type {Exercise} from 'src/models/exercise';
import {useTranslation} from 'react-i18next';
import {
  useAdminDeleteExerciseMutation,
  useAdminGetDeploymentsQuery,
} from 'src/slices/apiSlice';
import {toastSuccess, toastWarning} from 'src/components/Toaster';

const ExerciseCard = ({exercise}: {exercise: Exercise}) => {
  const {t} = useTranslation();
  const navigate = useNavigate();
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const {data: deployments} = useAdminGetDeploymentsQuery(exercise.id);
  const deploymentsExist = deployments && deployments.length > 0;
  const [deleteExercise,
    {isLoading, data, error}] = useAdminDeleteExerciseMutation();

  const handleCardClick = () => {
    if (!isLoading) {
      navigate(exercise.id);
    }
  };

  useEffect(() => {
    if (data) {
      toastSuccess(t('exercises.deleteSuccess', {
        exerciseName: exercise.name,
      }));
    }
  }, [data, exercise.name, t]);

  useEffect(() => {
    if (error) {
      toastWarning(t('exercises.deleteFail', {
        exerciseName: exercise.name,
      }));
    }
  }, [error, exercise.name, t]);

  const onMouseOver = () => {
    if (deploymentsExist) {
      setIsPopoverOpen(!isPopoverOpen);
    }
  };

  return (
    <Card interactive elevation={2} onClick={handleCardClick}>
      <div className='flex flex-row justify-between'>
        <H2>{exercise.name}</H2>
        <Tooltip
          content='This exercise has active deployments!'
          disabled={!deploymentsExist}
        >
          <div
            onMouseLeave={() => {
              setIsPopoverOpen(false);
            }}
          >
            <AnchorButton
              large
              intent='danger'
              disabled={isLoading || deploymentsExist}
              onClick={async event => {
                event.stopPropagation();
                await deleteExercise({
                  exerciseId: exercise.id,
                });
              }}
              onMouseOver={onMouseOver}
            >
              {isLoading ? t('common.deleting') : t('common.delete')}
            </AnchorButton>
          </div>
        </Tooltip>

      </div>
    </Card>
  );
};

export default ExerciseCard;
