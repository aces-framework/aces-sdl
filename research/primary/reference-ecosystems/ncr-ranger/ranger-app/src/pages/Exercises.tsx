import React from 'react';
import List from 'src/components/Exercise/List';
import PageHolder from 'src/components/PageHolder';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import type {NewExercise} from 'src/models/exercise';
import {useAdminAddExerciseMutation} from 'src/slices/apiSlice';
import Header from 'src/components/Header';
import {useTranslation} from 'react-i18next';
import AddDialog from 'src/components/Exercise/AddDialog';

const Exercise = () => {
  const {t} = useTranslation();
  const [addExercise, _newExercise] = useAdminAddExerciseMutation();
  const addNewExercise = async (newExercise: NewExercise) => {
    try {
      const exercise = await addExercise(newExercise).unwrap();
      if (exercise) {
        toastSuccess(t(
          'exercises.addingSuccess',
          {exerciseName: exercise.name},
        ));
      }
    } catch {
      toastWarning(t(
        'exercises.addingFail',
      ));
    }
  };

  return (
    <PageHolder>
      <Header
        headerTitle={t('exercises.title')}
        buttonTitle={t('exercises.add')}
        onSubmit={async (newExercise: NewExercise) => {
          await addNewExercise(newExercise);
        }}
      >
        <AddDialog
          title={t('exercises.add')}
        />
      </Header>
      <List/>
    </PageHolder>
  );
};

export default Exercise;
