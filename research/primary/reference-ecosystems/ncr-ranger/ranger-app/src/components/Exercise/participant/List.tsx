import React from 'react';
import {useParticipantGetExercisesQuery} from 'src/slices/apiSlice';
import humanInterval from 'human-interval';
import {sortByProperty} from 'sort-by-property';
import {H1, Spinner} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import ExerciseDeployments from './ExerciseDeployments';

const ExerciseList = () => {
  const {
    data: potentialExercises, isLoading,
  } = useParticipantGetExercisesQuery(
    undefined,
    {pollingInterval: humanInterval('5 seconds')},
  );

  const {t} = useTranslation();
  let exercises = potentialExercises ?? [];
  exercises = exercises.slice().sort(sortByProperty('updatedAt', 'desc'));

  if (isLoading) {
    return (
      <div className='flex flex-col items-center justify-center space-y-4 min-h-screen'>
        <H1 className='text-2xl font-bold'>
          {t('exercises.loadingExercises')}
        </H1>
        <Spinner/>
      </div>
    );
  }

  return (
    <div className='flex flex-col gap-8'>
      {exercises.map(exercise => (
        <ExerciseDeployments key={exercise.id} exercise={exercise}/>
      ))}
    </div>
  );
};

export default ExerciseList;
