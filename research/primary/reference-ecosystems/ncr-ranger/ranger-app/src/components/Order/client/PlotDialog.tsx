import {
  Button,
  Classes,
  Dialog,
  DialogBody,
  DialogFooter,
  H2,
} from '@blueprintjs/core';
import React, {useEffect} from 'react';
import {useFieldArray, useForm} from 'react-hook-form';
import {useTranslation} from 'react-i18next';
import DialogDateTimeInput from 'src/components/Form/DialogDateTimeInput';
import DialogMultiSelect from 'src/components/Form/DialogMultiSelect';
import DialogSelect from 'src/components/Form/DialogSelect';
import DialogTextArea from 'src/components/Form/DialogTextArea';
import DialogTextInput from 'src/components/Form/DialogTextInput';
import {type Order, type NewPlot, type Plot} from 'src/models/order';

const PlotDialog = (
  {
    isOpen,
    crossClicked,
    onSubmit,
    editablePlot,
    order,
  }: {
    isOpen: boolean;
    crossClicked: () => void;
    onSubmit: (formContent: NewPlot) => void;
    editablePlot?: Plot;
    order: Order;
  },
) => {
  const {t} = useTranslation();

  const {handleSubmit, control, reset} = useForm<NewPlot>({
    defaultValues: {
      name: '',
      description: '',
      startTime: '',
      endTime: '',
      plotPoints: [],
    },
  });

  useEffect(() => {
    reset({
      name: editablePlot?.name ?? '',
      description: editablePlot?.description ?? '',
      startTime: editablePlot?.startTime ?? '',
      endTime: editablePlot?.endTime ?? '',
      plotPoints: [],
    });
  }, [editablePlot, reset]);

  const onHandleSubmit = async (formContent: NewPlot) => {
    if (formContent.startTime.length > 23) {
      formContent.startTime = formContent.startTime.slice(0, -5);
    }

    if (formContent.endTime.length > 23) {
      formContent.endTime = formContent.endTime.slice(0, -5);
    }

    // eslint-disable-next-line @typescript-eslint/prefer-for-of
    for (let index = 0; index < formContent.plotPoints.length; index += 1) {
      const plotPoint = formContent.plotPoints[index];

      if (plotPoint.triggerTime.length > 23) {
        plotPoint.triggerTime = plotPoint.triggerTime.slice(0, -5);
      }
    }

    onSubmit(formContent);
    reset();
  };

  const {
    fields: plotPointFields, append: appendPlotPoint, remove: removePlotPoint,
  } = useFieldArray({
    control,
    name: 'plotPoints',
  });
  const objectivesExist = order.trainingObjectives && order.trainingObjectives.length > 0;

  return (
    <Dialog
      isOpen={isOpen}
    >
      <div className={Classes.DIALOG_HEADER}>
        <H2>{t('orders.plotElement.add')}</H2>
        <Button
          small
          minimal
          icon='cross'
          onClick={() => {
            crossClicked();
          }}/>
      </div>
      <form onSubmit={handleSubmit(onHandleSubmit)}>
        <DialogBody>
          <DialogTextInput<NewPlot>
            controllerProps={{
              control,
              name: 'name',
              rules: {
                required: t('orders.plotElement.nameRequired') ?? '',
                maxLength: {
                  value: 255,
                  message: t('orders.plotElement.nameMaxLength'),
                },
              },
            }}
            id='name'
            label={t('orders.plotElement.name')}
          />
          <DialogTextArea<NewPlot>
            textAreaProps={{
              fill: true,
              autoResize: true,
            }}
            controllerProps={{
              control,
              name: 'description',
              rules: {
                maxLength: {
                  value: 3000,
                  message: t('orders.plotElement.descriptionMaxLength'),
                },
              },
            }}
            id='description'
            label={t('orders.plotElement.description')}
          />
          <DialogDateTimeInput<NewPlot>
            controllerProps={{
              control,
              name: 'startTime',
              rules: {
                required: t('orders.plotElement.timeRequired') ?? '',
              },
            }}
            id='startTime'
            label={t('orders.plotElement.startTime')}
          />
          <DialogDateTimeInput<NewPlot>
            controllerProps={{
              control,
              name: 'endTime',
              rules: {
                required: t('orders.plotElement.timeRequired') ?? '',
              },
            }}
            id='endTime'
            label={t('orders.plotElement.endTime')}
          />
          <div className='flex justify-end'>
            <div className='flex gap-2'>
              <Button
                minimal
                intent='primary'
                icon='plus'
                onClick={() => {
                  appendPlotPoint({
                    name: '',
                    description: '',
                    objectiveId: '',
                    structureIds: [],
                    triggerTime: '',
                  });
                }}
              >
                {t('orders.plotElement.addNewPlotPoint')}
              </Button>
            </div>
          </div>
          <div className='flex flex-col gap-6 mt-2'>
            {plotPointFields.map((field, index) => (
              <React.Fragment key={field.id}>
                <div className='flex gap-6 items-start'>
                  <div className='grow flex flex-col gap-1'>
                    <DialogTextInput<NewPlot>
                      controllerProps={{
                        control,
                        name: `plotPoints.${index}.name`,
                        rules: {
                          required: t('orders.plotElement.plotPointNameRequired') ?? '',
                          maxLength: {
                            value: 255,
                            message: t('orders.plotElement.plotPointNameMaxLength'),
                          },
                        },
                        defaultValue: '',
                      }}
                      id={`plotPoint.name.${index}`}
                      label={t('orders.plotElement.plotPointName')}
                    />
                    <DialogTextArea<NewPlot>
                      textAreaProps={{
                        fill: true,
                        autoResize: true,
                      }}
                      controllerProps={{
                        control,
                        name: `plotPoints.${index}.description`,
                        rules: {
                          maxLength: {
                            value: 3000,
                            message: t('orders.plotElement.plotPointDescriptionMaxLength'),
                          },
                        },
                      }}
                      id={`plotPoint.description.${index}`}
                      label={t('orders.plotElement.plotPointDescription')}
                    />
                    <DialogSelect<NewPlot>
                      selectProps={{
                        disabled: !objectivesExist,
                        fill: true,
                        options: objectivesExist ? [
                          {
                            label: t('orders.plotElement.noObjective') ?? '',
                            value: '',
                          },
                          ...(order.trainingObjectives?.map(objective => ({
                            label: objective.objective,
                            value: objective.id,
                          })) ?? []),
                        ] : [{
                          label: t('orders.plotElement.noPossibleObjectives') ?? '',
                          value: '',
                        }],
                      }}
                      controllerProps={{
                        control,
                        name: `plotPoints.${index}.objectiveId`,
                      }}
                      id={`plotPoint.environmentId.${index}`}
                      label={t('orders.plotElement.objective')}
                    />
                    <DialogDateTimeInput<NewPlot>
                      controllerProps={{
                        control,
                        name: `plotPoints.${index}.triggerTime`,
                        rules: {
                          required: t('orders.plotElement.timeRequired') ?? '',
                        },
                      }}
                      id={`plotPoint.triggerTime.${index}`}
                      label={t('orders.plotElement.triggerTime')}
                    />
                    <DialogMultiSelect<
                    NewPlot, `plotPoints.${number}.structureIds`, 'structureId'
                    >
                      control={control}
                      items={(order.structures ?? []).map(structure => ({
                        structureId: structure.id,
                      }))}
                      name={`plotPoints.${index}.structureIds`}
                      keyName='structureId'
                      textRenderer={item => {
                        const structure = (order.structures ?? []).find(
                          structure => structure.id === item.structureId,
                        );
                        return structure?.name ?? '';
                      }}
                      id={`plotPoints.${index}.structureIds`}
                      label={t('orders.plotElement.plotPointConnectedStructures')}
                    />
                  </div>
                  <Button
                    minimal
                    intent='danger'
                    className='shrink-0 '
                    icon='remove'
                    onClick={() => {
                      removePlotPoint(index);
                    }}/>
                </div>
                {plotPointFields.length < index + 1 ? (<hr/>) : null}
              </React.Fragment>
            ))}
          </div>
        </DialogBody>
        <DialogFooter
          actions={<Button intent='primary' type='submit' text={t('orders.submit')}/>}
        />
      </form>
    </Dialog>
  );
};

export default PlotDialog;
