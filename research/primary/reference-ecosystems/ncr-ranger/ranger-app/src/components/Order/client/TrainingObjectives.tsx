import {
  Button,
  Callout,
  Card,
  Elevation,
  H4,
  Tag,
} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastWarning} from 'src/components/Toaster';
import {
  type Order,
  type NewTrainingObjective,
  type TrainingObjective,
} from 'src/models/order';
import {
  useClientAddTrainingObjectiveMutation,
  useClientDeleteTrainingOrderMutation,
  useClientUpdateTrainingObjectiveMutation,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import TrainingObjectiveDialog from './TrainingObjectiveDialog';

const TrainingObjectives = ({order, isEditable}: {order: Order; isEditable: boolean}) => {
  const {t} = useTranslation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [addTrainingObjective, {error}] = useClientAddTrainingObjectiveMutation();
  const [deleteTrainingObjective, {error: deleteError}] = useClientDeleteTrainingOrderMutation();
  const [updateTrainingObjective, {error: updateError}]
    = useClientUpdateTrainingObjectiveMutation();
  const trainingObjectives = order.trainingObjectives?.slice()
    .sort(sortByProperty('objective', 'asc')) ?? [];
  const [editedTrainingObjective, setEditedTrainingObjective]
    = useState<TrainingObjective | undefined>();

  useEffect(() => {
    if (error) {
      toastWarning(t(
        'orders.trainingObjective.failedtoAdd',
      ));
    }
  }, [error, t]);

  useEffect(() => {
    if (deleteError) {
      toastWarning(t(
        'orders.trainingObjective.failedToDelete',
      ));
    }
  }, [deleteError, t]);

  useEffect(() => {
    if (updateError) {
      toastWarning(t(
        'orders.trainingObjective.failedToUpadate',
      ));
    }
  }, [updateError, t]);

  const onHandleSubmit = async (formContent: NewTrainingObjective) => {
    if (editedTrainingObjective) {
      await updateTrainingObjective({
        newTrainingObjective: formContent,
        orderId: order.id,
        trainingObjectiveId: editedTrainingObjective.id,
      });
    } else {
      await addTrainingObjective({newTrainingObjective: formContent, orderId: order.id});
    }

    setIsDialogOpen(false);
    setEditedTrainingObjective(undefined);
  };

  return (
    <>
      <TrainingObjectiveDialog
        crossClicked={() => {
          setIsDialogOpen(false);
        }}
        isOpen={isDialogOpen}
        editableTrainingObjective={editedTrainingObjective}
        onSubmit={onHandleSubmit}
      />
      <Callout intent='primary' icon='info-sign'>
        {t('orders.trainingObjective.explenation')}
      </Callout>
      <div className='mt-4 flex gap-4 justify-between items-start'>
        <div className='flex flex-col gap-4 grow'>
          {trainingObjectives.map(trainingObjective => {
            const threats = trainingObjective.threats.slice()
              .sort(sortByProperty('threat', 'asc')) ?? [];

            return (
              <Card key={trainingObjective.id} className='min-w-0' elevation={Elevation.TWO}>
                <H4
                  className='truncate max-w-xl'
                >
                  {trainingObjective.objective}
                </H4>
                <div className='flex flex-wrap gap-4'>
                  {threats.map(threat => (
                    <Tag
                      key={threat.id}
                      large
                      minimal
                      className='truncate max-w-xl'
                      intent='primary'
                    >
                      {threat.threat}
                    </Tag>
                  ))}
                </div>
                <div className='flex mt-4 gap-2 justify-end'>
                  <Button
                    intent='danger'
                    disabled={!isEditable}
                    onClick={async () => {
                      await deleteTrainingObjective({
                        orderId: order.id,
                        trainingObjectiveId: trainingObjective.id,
                      });
                    }}
                  >
                    {t('common.delete')}
                  </Button>
                  <Button
                    disabled={!isEditable}
                    intent='warning'
                    onClick={() => {
                      setEditedTrainingObjective(trainingObjective);
                      setIsDialogOpen(true);
                    }}
                  >
                    {t('common.edit')}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
        <Button
          large
          className='shrink-0'
          disabled={!isEditable}
          intent='primary'
          onClick={() => {
            setEditedTrainingObjective(undefined);
            setIsDialogOpen(true);
          }}
        >
          {t('orders.trainingObjective.add')}
        </Button>
      </div>
    </>
  );
};

export default TrainingObjectives;

