import type React from 'react';
import {useCallback, useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import type {Banner, Exercise} from 'src/models/exercise';
import {skipToken} from '@reduxjs/toolkit/query';
import {Button, Callout, FormGroup} from '@blueprintjs/core';
import {type SubmitHandler, useForm} from 'react-hook-form';
import {
  useAdminAddBannerMutation,
  useAdminDeleteBannerMutation,
  useAdminGetBannerContentFromPackageQuery,
  useAdminGetBannerQuery,
  useAdminGetDeputyPackagesQuery,
  useAdminUpdateBannerMutation,
} from 'src/slices/apiSlice';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import {type Package} from 'src/models/package';
import ContentIFrame from 'src/components/ContentIFrame';
import humanInterval from 'human-interval';
import PackageDialog from './PackageDialog';

const BannerView = ({exercise}: {exercise: Exercise}) => {
  const {t} = useTranslation();
  const {data: bannerFromDatabase} = useAdminGetBannerQuery(exercise?.id ?? skipToken);
  const {data: bannerPackages}
    = useAdminGetDeputyPackagesQuery('banner', {pollingInterval: humanInterval('5 seconds')});
  const [addBanner, {error: addError}] = useAdminAddBannerMutation();
  const [updateBanner, {error: updateError}] = useAdminUpdateBannerMutation();
  const [deleteBanner, {error: deleteError}] = useAdminDeleteBannerMutation();

  const [bannerExistsInDatabase, setBannerExistsInDatabase] = useState(false);
  const [bannerOnPage, setBannerOnPage] = useState<Banner | undefined>(undefined);
  const [addSuccess, setAddSuccess] = useState<boolean>(false);
  const [updateSuccess, setUpdateSuccess] = useState<boolean>(false);
  const [deleteSuccess, setDeleteSuccess] = useState<boolean>(false);
  const [isPackageSelectOpen, setIsPackageSelectOpen] = useState(false);
  const {handleSubmit} = useForm<Banner>();
  const [selectedPackageInfo, setSelectedPackageInfo] = useState({
    name: '',
    version: '',
  });
  const {data: bannerPackageContent, isError: isBannerPackageFetchError}
    = useAdminGetBannerContentFromPackageQuery(selectedPackageInfo, {
      skip: !selectedPackageInfo.name || !selectedPackageInfo.version,
    });

  const handlePackageSelect = useCallback((selectedPackage: Package | undefined) => {
    if (selectedPackage) {
      setSelectedPackageInfo({name: selectedPackage.name, version: selectedPackage.version});
    }
  }, []);

  useEffect(() => {
    if (bannerFromDatabase) {
      setBannerOnPage(bannerFromDatabase);
      setBannerExistsInDatabase(true);
    }
  }, [bannerFromDatabase]);

  useEffect(() => {
    if (bannerPackageContent) {
      setBannerOnPage(bannerPackageContent);
      toastSuccess(t('exercises.package.success'));
    }
  }, [bannerPackageContent, t]);

  useEffect(() => {
    if (isBannerPackageFetchError) {
      toastWarning(t('exercises.package.fail'));
    }
  }, [isBannerPackageFetchError, t]);

  useEffect(() => {
    if (addSuccess) {
      toastSuccess(t('banners.createSuccess'));
      setAddSuccess(false);
    } else if (updateSuccess) {
      toastSuccess(t('banners.updateSuccess'));
      setUpdateSuccess(false);
    } else if (deleteSuccess) {
      toastSuccess(t('banners.deleteSuccess'));
      setDeleteSuccess(false);
    }
  }, [addSuccess, updateSuccess, deleteSuccess, t]);

  useEffect(() => {
    if (addError) {
      if ('data' in addError) {
        toastWarning(t('banners.createFail', {
          errorMessage: JSON.stringify(addError.data),
        }));
      } else {
        toastWarning(t('banners.createFailWithoutMessage'));
      }
    } else if (updateError) {
      if ('data' in updateError) {
        toastWarning(t('banners.updateFail', {
          errorMessage: JSON.stringify(updateError.data),
        }));
      } else {
        toastWarning(t('banners.updateFailWithoutMessage'));
      }
    } else if (deleteError) {
      if ('data' in deleteError) {
        toastWarning(t('banners.deleteFail', {
          errorMessage: JSON.stringify(deleteError.data),
        }));
      } else {
        toastWarning(t('banners.deleteFailWithoutMessage'));
      }
    }
  }, [addError, updateError, deleteError, t]);

  const onCreate: SubmitHandler<Banner> = async () => {
    if (bannerOnPage) {
      const result = await addBanner({newBanner: bannerOnPage, exerciseId: exercise.id});
      if ('data' in result) {
        setBannerOnPage(result.data);
        setBannerExistsInDatabase(true);
        setAddSuccess(true);
      }
    }
  };

  const onUpdate: SubmitHandler<Banner> = async () => {
    if (bannerOnPage) {
      const result = await updateBanner({updatedBanner: bannerOnPage, exerciseId: exercise.id});
      if ('data' in result) {
        setBannerOnPage(result.data);
        setBannerExistsInDatabase(true);
        setUpdateSuccess(true);
      }
    }
  };

  const onDelete: SubmitHandler<Banner> = async () => {
    await deleteBanner({exerciseId: exercise.id})
      .then(() => {
        setBannerOnPage(undefined);
      })
      .then(() => {
        setBannerExistsInDatabase(false);
      })
      .then(() => {
        setDeleteSuccess(true);
      });
  };

  return (
    <div className='mb-8'>
      <FormGroup
        labelFor='sdl-schema'
        label={
          <Callout intent='primary' title={t('exercises.bannerDocumentation') ?? ''}>
            <span>{t('exercises.easeBannerCreation')}</span>
            <a
              className='underline text-blue-500'
              href='https://documentation.opencyberrange.ee/docs/deputy/package/#banner'
              target='_blank'
              rel='noopener noreferrer'
            >
              {t('exercises.bannerGuide')}
            </a>
          </Callout>
        }
      />
      { bannerPackages && (
        <>
          <Button
            className='mb-4'
            icon='add'
            intent='success'
            text={t('exercises.package.getBannerPackage')}
            onClick={() => {
              setIsPackageSelectOpen(true);
            }}
          />
          <PackageDialog
            isOpen={isPackageSelectOpen}
            exercisePackages={bannerPackages}
            onClose={() => {
              setIsPackageSelectOpen(false);
            }}
            onPackageSelect={handlePackageSelect}
          />
        </>
      )}
      <form
        onSubmit={bannerExistsInDatabase ? handleSubmit(onUpdate) : handleSubmit(onCreate)}
        onReset={handleSubmit(onDelete)}
      >
        <p className='mb-4'>
          {bannerOnPage?.name && (
            <span className='font-medium'>{t('banners.name')}: {bannerOnPage.name}</span>
          )}
          {!bannerOnPage?.name && (
            t('exercises.noBanner')
          )}
        </p>
        <ContentIFrame content={bannerOnPage?.content}/>
        <div className='flex justify-end mt-[1rem] gap-[0.5rem]'>
          <Button
            large
            className='gap-[2rem]'
            type='submit'
            intent='primary'
            text={bannerExistsInDatabase ? t('update') : t('create')}
          />
          {bannerOnPage && (
            <Button
              large
              className='gap-[2rem]'
              type='reset'
              intent='danger'
              text={t('delete')}
            />
          )}
        </div>
      </form>
    </div>
  );
};

export default BannerView;
