import {Button, ButtonGroup, Callout} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import Accordion from 'src/components/Accordion';
import AccordionGroup from 'src/components/AccordionGroup';
import PageHolder from 'src/components/PageHolder';
import {ExerciseRole, ExerciseRoleOrder} from 'src/models/scenario';
import {getRoleColor} from 'src/utils';
import {t} from 'i18next';
import {skipToken} from '@reduxjs/toolkit/query';
import {
  useAdminGetManualMetricsQuery,
  useAdminUpdateMetricMutation,
} from 'src/slices/apiSlice';
import {
  type ManualMetric,
  type UpdateManualMetric,
} from 'src/models/manualMetric';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import MetricScoringForm from './MetricScoringForm';

const MetricScorer = ({exerciseId, deploymentId}:
{
  exerciseId: string;
  deploymentId: string;
}) => {
  const [selectedRole, setSelectedRole] = useState<ExerciseRole | undefined>(undefined);
  const handleRoleButtonClick = (role: ExerciseRole) => {
    setSelectedRole(role);
  };

  const {data: manualMetrics} = useAdminGetManualMetricsQuery(exerciseId && deploymentId
    ? {exerciseId, deploymentId} : skipToken);
  const defaultRole: ExerciseRole = manualMetrics?.[0]?.role ?? ExerciseRole.Blue;
  const [updateManualMetric, {isSuccess: isUpdateMetricSuccess}] = useAdminUpdateMetricMutation();

  const handleManualMetricUpdate = async (
    metric: ManualMetric, updateMetricForm: UpdateManualMetric) => {
    try {
      await updateManualMetric({
        exerciseId: metric.exerciseId,
        deploymentId: metric.deploymentId,
        metricId: metric.id,
        manualMetricUpdate: updateMetricForm,
      });
    } catch {
      toastWarning(t('metricScoring.errors.updateFailed'));
    }
  };

  useEffect(() => {
    if (isUpdateMetricSuccess) {
      toastSuccess(t('metricScoring.updateSuccess'));
    }
  }, [isUpdateMetricSuccess]);

  useEffect(() => {
    if (!selectedRole && manualMetrics && manualMetrics.length > 0) {
      setSelectedRole(defaultRole);
    }
  }, [selectedRole, manualMetrics, defaultRole]);

  if (manualMetrics && manualMetrics.length > 0) {
    const filteredMetrics = manualMetrics?.filter(metric =>
      metric.role === selectedRole
      || metric.role === defaultRole) ?? [];

    const sortedAvailableRoles
    = Array.from(new Set(filteredMetrics.map(metric => metric.role)))
      .sort((roleA, roleB) => ExerciseRoleOrder[roleA] - ExerciseRoleOrder[roleB]);

    return (
      <PageHolder>
        <div className='flex justify-center space-x-4'>
          <ButtonGroup fill>
            {sortedAvailableRoles.map(role => (
              <Button
                key={role}
                style={{backgroundColor: selectedRole === role ? getRoleColor(role) : 'gainsboro'}}
                active={role === selectedRole}
                className='rounded-full mb-4'
                onClick={() => {
                  handleRoleButtonClick(role);
                }}
              >
                <span className='font-bold text-white'> {role} {t('common.team')} </span>
              </Button>
            ))}
          </ButtonGroup>
        </div>
        <AccordionGroup>
          {manualMetrics.map(metric => (
            <Accordion
              key={metric.id}
              className='mb-4 p-2 border-2 border-slate-300 shadow-md'
              title={`${metric.name ?? metric.sdlKey} - ${metric.entitySelector}`}
            >
              <MetricScoringForm
                exerciseId={exerciseId}
                deploymentId={deploymentId}
                metric={metric}
                onSubmit={async metricScorerForm => {
                  await handleManualMetricUpdate(metric, metricScorerForm);
                }}
              />
            </Accordion>
          ))}
        </AccordionGroup>
      </PageHolder>
    );
  }

  return (
    <PageHolder>
      <Callout title={t('metricScoring.noManualMetrics') ?? ''}/>
    </PageHolder>

  );
};

export default MetricScorer;
