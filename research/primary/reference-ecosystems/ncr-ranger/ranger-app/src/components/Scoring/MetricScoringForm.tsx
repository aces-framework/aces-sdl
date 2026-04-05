import type React from 'react';
import {
  Button,
  FormGroup,
  Intent,
  NumericInput,
  TextArea,
} from '@blueprintjs/core';
import {useState} from 'react';
import {Controller, useForm} from 'react-hook-form';
import {
  type UpdateManualMetric,
  type ManualMetric,
} from 'src/models/manualMetric';
import {toastWarning} from 'src/components/Toaster';
import {useTranslation} from 'react-i18next';
import {useLazyAdminGetManualMetricArtifactQuery} from 'src/slices/apiSlice';

const MetricScoringForm = ({exerciseId, deploymentId, metric, onSubmit}:
{
  exerciseId: string;
  deploymentId: string;
  metric: ManualMetric;
  onSubmit: ({textSubmission, score}: UpdateManualMetric) => void;
}) => {
  const {handleSubmit, control}
  = useForm<UpdateManualMetric>({
    defaultValues: {
      textSubmission: metric.textSubmission ?? '',
      score: metric.score ?? 0,
    },
  });
  const {t} = useTranslation();
  const [loading, setLoading] = useState(false);
  const [getArtifactFetchUrl] = useLazyAdminGetManualMetricArtifactQuery();

  const handleDownload = async () => {
    setLoading(true);
    try {
      const artifactData = await getArtifactFetchUrl(
        {deploymentId, exerciseId, metricId: metric.id});

      if (artifactData.data?.url) {
        const artifactResponse = await fetch(artifactData.data?.url);
        const blob = await artifactResponse.blob();
        const filename = artifactData.data?.filename;
        if (blob && filename) {
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = filename;
          link.click();
        }
      } else {
        toastWarning(t('metricScoring.errors.downloadFailed'));
      }
    } catch {
      toastWarning(t('metricScoring.errors.downloadFailed'));
    }

    setLoading(false);
  };

  const onHandleSubmit = (formContent: UpdateManualMetric) => {
    if (onSubmit) {
      if (formContent.score === undefined) {
        toastWarning(t('metricScoring.errors.scoreNotSet'));
      } else {
        onSubmit(formContent);
      }
    }
  };

  const validateScore = (value: number | undefined) => {
    if (!value || value < 0 || value > metric.maxScore) {
      return `${t('metricScoring.errors.scoreValue', {maxScore: metric.maxScore})} `;
    }

    return true;
  };

  return (
    <div>
      <form
        className='flex flex-col'
        onSubmit={handleSubmit(onHandleSubmit)}
      >
        <div className='flex mt-4 items-center space-x-2'>
          <Button
            large
            intent='primary'
            disabled={!metric.hasArtifact || loading}
            onClick={async () => handleDownload()}
          >
            {loading ? t('metricScoring.downloadButtonLoading') : t('metricScoring.downloadButton')}
          </Button>

          <TextArea
            readOnly
            placeholder={t('metricScoring.textSubmissionPlaceholder') ?? ''}
            className='text-gray-500 h-96 max-h-40 w-96'
            value={metric.textSubmission ?? ''}
          />

          <Controller
            control={control}
            name='score'
            rules={{validate: validateScore}}
            render={({
              field: {onChange, onBlur, ref, value}, fieldState: {error},
            }) => {
              const intent = error ? Intent.DANGER : Intent.NONE;
              return (
                <FormGroup
                  helperText={error?.message}
                  intent={intent}
                  labelInfo={`(Max: ${metric.maxScore})`}
                  label='Score'
                >
                  <div className='flex flex-row items-center'>
                    <NumericInput
                      fill
                      large
                      placeholder={t('metricScoring.scorePlaceholder') ?? ''}
                      buttonPosition='none'
                      min={0}
                      max={metric.maxScore}
                      intent={intent}
                      value={value}
                      inputRef={ref}
                      id='score'
                      onValueChange={valueAsNumber => {
                        if (!Number.isNaN(valueAsNumber) && valueAsNumber >= 0) {
                          onChange(valueAsNumber);
                        }
                      }}
                      onBlur={onBlur}
                    />
                    <Button
                      large
                      type='submit'
                      className='m-2'
                      intent='primary'
                    >
                      {t('common.submit')}
                    </Button>
                  </div>
                </FormGroup>
              );
            }}
          />
        </div>
      </form>
    </div>
  );
};

export default MetricScoringForm;
