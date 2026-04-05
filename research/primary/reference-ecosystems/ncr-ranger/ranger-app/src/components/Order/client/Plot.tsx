import {
  Button,
  Callout,
  Card,
  CardList,
  Elevation,
  H3,
  H4,
  Tag,
} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastWarning} from 'src/components/Toaster';
import {type Order, type Plot, type NewPlot} from 'src/models/order';
import {
  useClientAddPlotMutation,
  useClientDeletePlotMutation,
  useClientUpdatePlotMutation,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import PlotDialog from './PlotDialog';

const PlotElement = ({order, isEditable: isUserClient}: {order: Order; isEditable: boolean}) => {
  const {t} = useTranslation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [addPlot, {error}] = useClientAddPlotMutation();
  const [deletePlot, {error: deleteError}] = useClientDeletePlotMutation();
  const [updatePlot, {error: updateError}]
          = useClientUpdatePlotMutation();
  const [editedPlot, setEditedPlot]
          = useState<Plot | undefined>();
  const {plots: potentialPlots} = order;
  const sortedPlots = [...(potentialPlots ?? [])]
    .sort(sortByProperty('name', 'desc'));

  useEffect(() => {
    if (error) {
      toastWarning(t(
        'orders.plotElement.failedToAdd',
      ));
    }
  }, [error, t]);

  useEffect(() => {
    if (deleteError) {
      toastWarning(t(
        'orders.plotElement.failedToDelete',
      ));
    }
  }, [deleteError, t]);

  useEffect(() => {
    if (updateError) {
      toastWarning(t(
        'orders.plotElement.failedToUpdate',
      ));
    }
  }, [updateError, t]);

  const onHandleSubmit = async (formContent: NewPlot) => {
    setIsDialogOpen(false);
    if (editedPlot) {
      await updatePlot({
        newPlot: {
          ...editedPlot,
          ...formContent,
        },
        orderId: order.id,
        plotId: editedPlot.id,
      });
    } else {
      await addPlot({
        newPlot: formContent,
        orderId: order.id,
      });
    }

    setEditedPlot(undefined);
  };

  const objectives = order.trainingObjectives ?? [];
  const structures = order.structures ?? [];

  return (
    <>
      <PlotDialog
        crossClicked={() => {
          setIsDialogOpen(false);
        }}
        isOpen={isDialogOpen}
        editablePlot={editedPlot}
        order={order}
        onSubmit={onHandleSubmit}
      />
      <Callout intent='primary' icon='info-sign'>
        {t('orders.plotElement.explenation')}
      </Callout>
      <Callout className='mt-2' intent='primary' icon='info-sign'>
        {t('orders.plotElement.plotPointExplenation')}
      </Callout>
      <div className='mt-4 flex gap-4 justify-between items-start'>
        <div className='flex flex-col gap-4 grow'>
          {sortedPlots.map(plot => (
            <Card key={plot.id} className='min-w-0' elevation={Elevation.TWO}>
              <div className='flex gap-6'>
                <H3
                  className='truncate max-w-xl m-0'
                >
                  {plot.name}
                </H3>
                <div className='flex gap-2'>
                  <Tag
                    minimal
                    round
                    icon='time'
                  >
                    {(new Date(plot.startTime)).toLocaleString()}
                  </Tag>
                  -
                  <Tag
                    minimal
                    round
                    icon='time'
                  >
                    {(new Date(plot.endTime)).toLocaleString()}
                  </Tag>
                </div>
              </div>
              {plot.description && (
                <div className='flex flex-wrap gap-4 mt-2'>
                  <p>{plot.description}</p>
                </div>)}
              <CardList compact className='mt-4'>
                {plot.plotPoints.sort(sortByProperty('triggerTime', 'desc')).map(plotPoint => (
                  <Card key={plotPoint.id}>
                    <div className='flex flex-col items-start'>
                      <div className='flex gap-4 justify-end flex-wrap'>
                        <H4>{plotPoint.name}</H4>
                        {plotPoint.triggerTime && (
                          <Tag
                            minimal
                            round
                            icon='time'
                          >
                            {(new Date(plotPoint.triggerTime)).toLocaleString()}
                          </Tag>
                        )}
                        {plotPoint.objectiveId && (
                          <Tag
                            minimal
                            round
                            icon='flag'
                            intent='primary'
                          >
                            {objectives
                              .find(objective => objective.id === plotPoint.objectiveId)?.objective
                              ?? ''}
                          </Tag>
                        )}
                        {
                          plotPoint.structureIds.map(structureId => (
                            <Tag
                              key={structureId.structureId}
                              minimal
                              round
                              intent='success'
                              icon='layout'
                            >
                              {structures
                                .find(structure => structure.id === structureId.structureId)?.name
                                ?? ''}
                            </Tag>
                          ))
                        }
                      </div>
                      <div className='mt-2'>
                        {plotPoint.description}
                      </div>
                    </div>
                  </Card>
                ))}
              </CardList>
              <div className='flex mt-4 gap-2 justify-end'>
                <Button
                  disabled={!isUserClient}
                  intent='danger'
                  onClick={async () => {
                    await deletePlot({
                      orderId: order.id,
                      plotId: plot.id,
                    });
                  }}
                >
                  {t('common.delete')}
                </Button>
                <Button
                  disabled={!isUserClient}
                  intent='warning'
                  onClick={() => {
                    setEditedPlot(plot);
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
          disabled={!isUserClient}
          className='shrink-0'
          intent='primary'
          onClick={() => {
            setEditedPlot(undefined);
            setIsDialogOpen(true);
          }}
        >
          {t('orders.plotElement.add')}
        </Button>
      </div>
    </>
  );
};

export default PlotElement;
