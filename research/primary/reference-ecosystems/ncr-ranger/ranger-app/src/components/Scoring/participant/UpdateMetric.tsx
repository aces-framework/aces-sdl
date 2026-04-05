import type React from 'react';
import {Button, FileInput, TextArea, Tooltip} from '@blueprintjs/core';
import {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import {
  type UpdateManualMetric,
  type ManualMetric,
} from 'src/models/manualMetric';
import {
  useParticipantUpdateMetricMutation,
  useParticipantUploadMetricArtifactMutation,
} from 'src/slices/apiSlice';
import {ARTIFACT_FILETYPE_WHITELIST} from 'src/constants';
import {useSelector} from 'react-redux';
import {selectedEntity} from 'src/slices/userSlice';

const UpdateMetric = ({exerciseId, deploymentId, manualMetric, metricHasArtifact}:
{exerciseId: string;
  deploymentId: string;
  manualMetric: ManualMetric;
  metricHasArtifact: boolean;
}) => {
  const {t} = useTranslation();
  const entitySelector = useSelector(selectedEntity);
  const [updateMetric, {isSuccess: isUpdateMetricSuccess}] = useParticipantUpdateMetricMutation();
  const [addArtifact, {isSuccess: isAddArtifactSuccess}]
   = useParticipantUploadMetricArtifactMutation();
  const [artifactFile, setArtifactFile] = useState<File | undefined>(undefined);
  const [submissionText, setSubmissionText]
  = useState<string | undefined>(manualMetric.textSubmission);
  const [buttonIsDisabled, setButtonIsDisabled] = useState(true);
  const metricHasBeenScored = manualMetric.score !== null;
  const handleUpdateMetric
  = async (updateManualMetric: UpdateManualMetric) => {
    try {
      if (!entitySelector) {
        throw new Error('No entity selected');
      }

      if (artifactFile) {
        await addArtifact({
          exerciseId,
          deploymentId,
          metricId: manualMetric.id,
          artifactFile,
          entitySelector,
        });
      }

      await updateMetric({
        exerciseId,
        deploymentId,
        metricId: manualMetric.id,
        manualMetricUpdate: updateManualMetric,
        entitySelector,
      });
    } catch (error: unknown) {
      if (error instanceof Error) {
        toastWarning(t('metricScoring.errors.updateFailedWithMessage',
          {errorMessage: JSON.stringify(error.message)}));
      } else {
        toastWarning(t('metricScoring.errors.updateFailed'));
      }
    }
  };

  useEffect(() => {
    if (isUpdateMetricSuccess) {
      toastSuccess(t('metricScoring.updateSuccess'));
    }
  }, [isUpdateMetricSuccess, t]);

  useEffect(() => {
    if (isAddArtifactSuccess) {
      toastSuccess(t('metricScoring.artifactAdded'));
    }
  }, [isAddArtifactSuccess, t]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setArtifactFile(event.target.files[0]);
    }
  };

  useEffect(() => {
    const submissionTextIsUnchanged = submissionText === manualMetric.textSubmission;
    const artifactIsUndefined = artifactFile === undefined;
    setButtonIsDisabled((submissionTextIsUnchanged && artifactIsUndefined) || metricHasBeenScored);
  }, [submissionText, manualMetric, artifactFile, buttonIsDisabled, metricHasBeenScored]);

  return (
    <div>
      <div className='flex flex-col'>
        <div className='italic text-slate-600 p-2 self-center'>
          {t('metricScoring.score')}: {manualMetric.score
          ?? t('metricScoring.notScored')} / {manualMetric.maxScore}
        </div>
        <form
          className='flex mt-4 justify-between items-center'
        >

          <FileInput
            className='ml-4'
            id='artifact'
            disabled={metricHasBeenScored || !metricHasArtifact}
            inputProps={{accept: ARTIFACT_FILETYPE_WHITELIST}}
            text={artifactFile?.name ?? t('metricScoring.replaceArtifactPlaceholder')}
            buttonText={t('common.browse') ?? ''}
            onInputChange={handleFileChange}

          />
          <TextArea
            className='w-1/2'
            id='submissionText'
            name='submissionText'
            disabled={metricHasBeenScored}
            value={submissionText}
            placeholder={t('metricScoring.addSubmissionText') ?? ''}
            onChange={event => {
              setSubmissionText(event.target.value);
            }}/>

          <Tooltip
            content={manualMetric.score
              ? t('metricScoring.errors.alreadyScored') ?? ''
              : t('metricScoring.errors.notAltered') ?? ''}
            disabled={!buttonIsDisabled}
          >
            <Button
              className='mr-4'
              intent='primary'
              text={t('metricScoring.updateSubmissionButton') ?? ''}
              disabled={buttonIsDisabled}
              onClick={async () => handleUpdateMetric({
                textSubmission: submissionText,
              })}
            />
          </Tooltip>
        </form>
      </div>
    </div>
  );
};

export default UpdateMetric;
