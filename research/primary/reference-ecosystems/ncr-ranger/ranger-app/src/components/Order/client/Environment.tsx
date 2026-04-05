import {
  Button,
  Callout,
  Card,
  Elevation,
  H3,
  Tag,
} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastWarning} from 'src/components/Toaster';
import {
  type Order,
  type NewEnvironment,
  type Environment,
} from 'src/models/order';
import {
  useClientAddEnvironmentMutation,
  useClientDeleteEnvironmentMutation,
  useClientUpdateEnvironmentMutation,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import EnvironmentDialog from './EnvironmentDialog';

const EnvironmentElement = ({order, isEditable}: {order: Order; isEditable: boolean}) => {
  const {t} = useTranslation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [addEnvironment, {error}] = useClientAddEnvironmentMutation();
  const [deleteEnvironment, {error: deleteError}] = useClientDeleteEnvironmentMutation();
  const [updateEnvironment, {error: updateError}]
        = useClientUpdateEnvironmentMutation();
  const [editedEnvironment, setEditedEnvironment]
        = useState<Environment | undefined>();
  const {environments: potentialEnvironments} = order;
  const sortedEnvironments = [...(potentialEnvironments ?? [])]
    .sort(sortByProperty('name', 'desc'));

  useEffect(() => {
    if (error) {
      toastWarning(t(
        'orders.environmentElements.failedToAdd',
      ));
    }
  }, [error, t]);

  useEffect(() => {
    if (deleteError) {
      toastWarning(t(
        'orders.environmentElements.failedToDelete',
      ));
    }
  }, [deleteError, t]);

  useEffect(() => {
    if (updateError) {
      toastWarning(t(
        'orders.environmentElements.failedToUpdate',
      ));
    }
  }, [updateError, t]);

  const onHandleSubmit = async (formContent: NewEnvironment) => {
    setIsDialogOpen(false);
    if (editedEnvironment) {
      await updateEnvironment({
        newEnvironment: {
          ...editedEnvironment,
          ...formContent,
        },
        orderId: order.id,
        environmentId: editedEnvironment.id,
      });
    } else {
      await addEnvironment({
        newEnvironment: formContent,
        orderId: order.id,
      });
    }

    setEditedEnvironment(undefined);
  };

  return (
    <>
      <EnvironmentDialog
        crossClicked={() => {
          setIsDialogOpen(false);
        }}
        isOpen={isDialogOpen}
        editableEnvironment={editedEnvironment}
        onSubmit={onHandleSubmit}
      />
      <Callout intent='primary' icon='info-sign'>
        {t('orders.environmentElements.explenation')}
      </Callout>
      <div className='mt-4 flex gap-4 justify-between items-start'>
        <div className='flex flex-col gap-4 grow'>
          {sortedEnvironments.map(environment => (
            <Card key={environment.id} className='min-w-0' elevation={Elevation.TWO}>
              <div className='flex gap-2'>
                <H3
                  className='truncate max-w-xl m-0'
                >
                  {environment.name}
                </H3>
                <Tag
                  minimal
                  round
                  icon='cube'
                >
                  {environment.category}
                </Tag>
                <Tag
                  minimal
                  round
                >
                  <b>
                    {environment.size}
                  </b>
                </Tag>
              </div>
              <div className='flex flex-wrap gap-4 mt-4'>
                {(environment.strengths ?? []).map(strength => (
                  <Tag
                    key={strength.id}
                    large
                    minimal
                    className='truncate max-w-xl'
                    intent='success'
                  >
                    {strength.strength}
                  </Tag>
                ))}
                {(environment.weaknesses ?? []).map(weakness => (
                  <Tag
                    key={weakness.id}
                    large
                    minimal
                    className='truncate max-w-xl'
                    intent='danger'
                  >
                    {weakness.weakness}
                  </Tag>
                ))}
              </div>
              {environment.additionalInformation && (
                <div className='flex flex-wrap gap-4 mt-2'>
                  <p>{environment.additionalInformation}</p>
                </div>)}
              <div className='flex mt-4 gap-2 justify-end'>
                <Button
                  disabled={!isEditable}
                  intent='danger'
                  onClick={async () => {
                    await deleteEnvironment({
                      orderId: order.id,
                      environmentId: environment.id,
                    });
                  }}
                >
                  {t('common.delete')}
                </Button>
                <Button
                  disabled={!isEditable}
                  intent='warning'
                  onClick={() => {
                    setEditedEnvironment(environment);
                    setIsDialogOpen(true);
                  }}
                >
                  {t('common.edit')}
                </Button>
              </div>
            </Card>
          ))}
        </div>
        <Button
          large
          disabled={!isEditable}
          className='shrink-0'
          intent='primary'
          onClick={() => {
            setEditedEnvironment(undefined);
            setIsDialogOpen(true);
          }}
        >
          {t('orders.environmentElements.add')}
        </Button>
      </div>
    </>
  );
};

export default EnvironmentElement;

