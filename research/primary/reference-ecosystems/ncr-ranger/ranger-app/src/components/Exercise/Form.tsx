import type React from 'react';
import {useCallback, useEffect, useState} from 'react';
import type {SubmitHandler} from 'react-hook-form';
import {useForm, Controller} from 'react-hook-form';
import {
  Button,
  Callout,
  FormGroup,
  HTMLSelect,
  InputGroup,
  Intent,
  MenuItem,
} from '@blueprintjs/core';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import type {Exercise, UpdateExercise} from 'src/models/exercise';
import {type AdGroup} from 'src/models/groups';
import {
  useAdminCheckPackagesExistMutation,
  useAdminGetDeploymentGroupsQuery,
  useAdminGetDeputyPackagesQuery,
  useAdminGetExerciseSdlFromPackageQuery,
  useAdminGetGroupsQuery,
  useAdminUpdateExerciseMutation,
} from 'src/slices/apiSlice';
import Editor from '@monaco-editor/react';
import {useTranslation} from 'react-i18next';
import {Resizable} from 're-resizable';
import init, {
  parse_and_verify_sdl as parseAndVerifySDL,
} from '@open-cyber-range/wasm-sdl-parser';
import {Suggest} from '@blueprintjs/select';
import useResourceEstimation from 'src/hooks/useResourceEstimation';
import {type Package} from 'src/models/package';
import {type Scenario} from 'src/models/scenario';
import {getPackageSources} from 'src/utils/scenario';
import PackageDialog from './PackageDialog';

const ExerciseForm = ({exercise, onContentChange, children}:
{
  exercise: Exercise;
  onContentChange: (isChanged: boolean) => void;
  children?: React.ReactNode;
}) => {
  const {t} = useTranslation();
  const {handleSubmit, control, setValue, watch} = useForm<UpdateExercise>({
    defaultValues: {
      name: exercise.name,
      deploymentGroup: exercise.deploymentGroup,
      sdlSchema: exercise.sdlSchema ?? '',
      groupName: exercise.groupName ?? '',
    },
  });
  const {data: groups} = useAdminGetGroupsQuery();
  const {data: deploymentGroups} = useAdminGetDeploymentGroupsQuery();
  const {data: exercisePackages} = useAdminGetDeputyPackagesQuery('exercise');
  const {sdlSchema} = watch();
  const {totalRam, totalCpu, resourceEstimationError} = useResourceEstimation(sdlSchema);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedPackageInfo, setSelectedPackageInfo] = useState({
    name: '',
    version: '',
  });
  const {data: fetchedSdl, isError: isSdlFetchError}
  = useAdminGetExerciseSdlFromPackageQuery(selectedPackageInfo, {
    skip: !selectedPackageInfo.name || !selectedPackageInfo.version,
  });

  const handlePackageSelect = useCallback((selectedPackage: Package | undefined) => {
    if (selectedPackage) {
      setSelectedPackageInfo({name: selectedPackage.name, version: selectedPackage.version});
    }
  }, []);

  useEffect(() => {
    if (fetchedSdl) {
      setValue('sdlSchema', fetchedSdl);
      toastSuccess(t('exercises.package.success'));
    }
  }, [fetchedSdl, setValue, t, exercise.name]);

  useEffect(() => {
    if (isSdlFetchError) {
      toastWarning(t('exercises.package.fail'));
    }
  }, [isSdlFetchError, t]);

  useEffect(() => {
    const subscription = watch((value, {name, type}) => {
      if (name === 'sdlSchema' && type === 'change') {
        onContentChange(true);
      }
    });
    return () => {
      subscription.unsubscribe();
    };
  }, [watch, onContentChange]);

  const [updateExercise, {isSuccess, error}] = useAdminUpdateExerciseMutation();
  const [adminCheckPackagesExist] = useAdminCheckPackagesExistMutation();

  const onSubmit: SubmitHandler<UpdateExercise> = async exerciseUpdate => {
    let scenario: Scenario | undefined;
    if (exerciseUpdate.sdlSchema) {
      try {
        const parsedSdl = parseAndVerifySDL(exerciseUpdate.sdlSchema);
        scenario = JSON.parse(parsedSdl) as Scenario;
      } catch (error: any) {
        if (typeof error === 'string') {
          toastWarning(error);
        } else {
          toastWarning(t('exercises.sdlParsingFail'));
        }

        return;
      }
    }

    if (scenario) {
      const packageSources = getPackageSources(scenario);
      try {
        await adminCheckPackagesExist(packageSources).unwrap().then(async () => {
          await updateExercise({exerciseUpdate, exerciseId: exercise.id});
          onContentChange(false);
        },
        );
      } catch (error: any) {
        if ('data' in error) {
          toastWarning(t('exercises.packageCheckFail', {
            errorMessage: JSON.stringify(error.data),
          }));
        } else {
          toastWarning(t('exercises.packageCheckFail'));
        }
      }
    }
  };

  useEffect(() => {
    const initializeSdlParser = async () => {
      await init();
    };

    initializeSdlParser()
      .catch(() => {
        toastWarning(t('exercises.sdlParserInitFail'));
      });
  }, [t]);

  useEffect(() => {
    if (isSuccess) {
      toastSuccess(t('exercises.updateSuccess', {
        exerciseName: JSON.stringify(exercise.name),
      }));
    }
  }, [isSuccess, t, exercise.name]);

  useEffect(() => {
    if (error) {
      if ('data' in error) {
        toastWarning(t('exercises.updateFail', {
          errorMessage: JSON.stringify(error.data),
        }));
      } else {
        toastWarning(t('exercises.updateFail'));
      }
    }
  }, [error, t]);

  return (
    <form className='ExerciseForm' onSubmit={handleSubmit(onSubmit)}>
      <Controller
        control={control}
        name='name'
        rules={{required: t('exercises.mustHaveName') ?? ''}}
        render={({
          field: {onChange, onBlur, ref, value}, fieldState: {error},
        }) => {
          const intent = error ? Intent.DANGER : Intent.NONE;
          return (
            <FormGroup
              labelFor='execise-name'
              labelInfo={t('common.required')}
              helperText={error?.message}
              intent={intent}
              label={t('exercises.name')}
            >
              <InputGroup
                large
                intent={intent}
                value={value}
                inputRef={ref}
                id='execise-name'
                onChange={onChange}
                onBlur={onBlur}
              />
            </FormGroup>
          );
        }}
      />
      <Controller
        control={control}
        name='deploymentGroup'
        defaultValue={exercise.deploymentGroup}
        render={({
          field: {onChange, value},
        }) => (
          <FormGroup
            labelFor='deployment-group'
            labelInfo='(required)'
            label={t('exercises.group.title')}
          >
            <HTMLSelect
              large
              fill
              id='deployment-group'
              value={value}
              onChange={onChange}
            >
              {Object.keys((deploymentGroups ?? {})).map(groupName =>
                <option key={groupName}>{groupName}</option>)}
            </HTMLSelect>
          </FormGroup>
        )}
      />
      <Controller
        control={control}
        name='groupName'
        render={({
          field: {onBlur, ref, value, onChange}, fieldState: {error},
        }) => {
          const intent = error ? Intent.DANGER : Intent.NONE;
          const activeItem = groups?.find(group => group.name === value);
          return (
            <FormGroup
              labelFor='execise-group'
              helperText={error?.message}
              intent={intent}
              label={t('common.adGroup')}
            >
              <Suggest<AdGroup>
                inputProps={{
                  onBlur,
                  inputRef: ref,
                  placeholder: '',
                }}
                activeItem={activeItem}
                inputValueRenderer={item => item.name}
                itemPredicate={(query, item) =>
                  item.name.toLowerCase().includes(query.toLowerCase())}
                itemRenderer={(item, {handleClick, handleFocus}) => (
                  <MenuItem
                    key={item.id}
                    text={item.name}
                    onClick={handleClick}
                    onFocus={handleFocus}
                  />
                )}
                items={groups ?? []}
                noResults={
                  <MenuItem
                    disabled
                    text={t('common.noResults')}
                    roleStructure='listoption'/>
                }
                selectedItem={activeItem}
                onItemSelect={item => {
                  onChange(item.name);
                }}
              />
            </FormGroup>
          );
        }}
      />
      { exercisePackages && (
        <>
          <Button
            className='mb-4'
            icon='add'
            intent='success'
            text={t('exercises.package.getScenarioSDL')}
            onClick={() => {
              setIsOpen(true);
            }}
          />
          <PackageDialog
            isOpen={isOpen}
            exercisePackages={exercisePackages}
            onClose={() => {
              setIsOpen(false);
            }}
            onPackageSelect={handlePackageSelect}
          />
        </>
      )}
      <Controller
        control={control}
        name='sdlSchema'
        render={({
          field: {onChange, value}, fieldState: {error},
        }) => {
          const intent = error ? Intent.DANGER : Intent.NONE;
          return (
            <FormGroup
              labelFor='sdl-schema'
              helperText={error?.message}
              intent={intent}
              label={
                <Callout intent='primary' title={t('exercises.scenarioSDL') ?? ''}>
                  <span>{t('exercises.easeDevelopment')}</span>
                  <a
                    className='underline text-blue-500'
                    href='https://documentation.opencyberrange.ee/docs/sdl/reference'
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    {t('exercises.sdlGuide')}
                  </a>
                </Callout>
              }
            >
              <Resizable
                defaultSize={{
                  width: '100%',
                  height: '40vh',
                }}
                enable={{
                  bottom: true,
                }}
                className='h-[40vh] border border-b-8'
              >
                <Editor
                  value={value}
                  defaultLanguage='yaml'
                  onChange={onChange}
                />
              </Resizable>
              <div className='mt-4'>
                {resourceEstimationError && (
                  <Callout
                    intent='danger'
                    title={t('exercises.estimatedResourcesFail') ?? ''}
                  >
                    <span>{resourceEstimationError}</span>
                  </Callout>
                )}
                {typeof totalRam === 'string' && typeof totalCpu === 'number'
                && !resourceEstimationError && (
                  <Callout
                    title={t('exercises.estimatedResourcesTitle') ?? ''}
                  >
                    <span>
                      {t('exercises.estimatedResources', {
                        totalRam,
                        totalCpu,
                      })}
                    </span>
                  </Callout>
                )}
              </div>
            </FormGroup>
          );
        }}
      />
      <div className='flex justify-end mt-[1rem] gap-[0.5rem]'>
        {children}
        <Button
          large
          type='submit'
          intent='primary'
        >{t('common.submit')}
        </Button>
      </div>
    </form>

  );
};

export default ExerciseForm;
