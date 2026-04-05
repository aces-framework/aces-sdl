import React from 'react';
import {useAdminGetExercisesQuery} from 'src/slices/apiSlice';
import humanInterval from 'human-interval';
import {sortByProperty} from 'sort-by-property';
import ExerciseCard from './Card';

const ExerciseList = () => {
  const {
    data: potentialExercises,
  } = useAdminGetExercisesQuery(
    undefined,
    {pollingInterval: humanInterval('5 seconds')},
  );
  let exercises = potentialExercises ?? [];
  exercises = exercises.slice().sort(sortByProperty('updatedAt', 'desc'));

  return (
    <div className='flex flex-col gap-8'>
      {exercises.map(exercise => (
        <ExerciseCard key={exercise.id} exercise={exercise}/>
      ))}
    </div>

  );
};

export default ExerciseList;
