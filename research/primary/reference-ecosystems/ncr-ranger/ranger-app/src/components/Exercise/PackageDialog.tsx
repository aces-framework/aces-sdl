import type React from 'react';
import {useState} from 'react';
import {
  Button,
  Dialog,
  FormGroup,
  H4,
  HTMLSelect,
} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import {type Package} from 'src/models/package';

const PackageDialog = (
  {isOpen, exercisePackages, onClose, onPackageSelect}:
  {
    isOpen?: boolean;
    exercisePackages: Package[];
    onClose: () => void;
    onPackageSelect: (selectedPackage: Package | undefined) => void;
  },
) => {
  const {t} = useTranslation();
  const [selectedPackageName, setSelectedPackageName] = useState('');
  const [selectedVersion, setSelectedVersion] = useState('');

  const packagesWithVersions = exercisePackages
    .reduce<Record<string, string[]>>((accumulator, currentPackage) => {
    if (!accumulator[currentPackage.name]) {
      accumulator[currentPackage.name] = [];
    }

    accumulator[currentPackage.name].push(currentPackage.version);

    return accumulator;
  }, {});

  const handlePackageChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPackageName(event.target.value);
    setSelectedVersion('');
  };

  const handleAddClick = () => {
    const selectedPackage = exercisePackages?.find(
      exercisePackage => exercisePackage.name === selectedPackageName
      && exercisePackage.version === selectedVersion);
    onPackageSelect(selectedPackage);
    onClose();
  };

  if (isOpen && packagesWithVersions) {
    return (
      <Dialog isOpen={isOpen} onClose={onClose}>
        <div className='bp5-dialog-header'>
          <H4>{t('exercises.package.getScenarioSDL')}</H4>
          <Button
            small
            minimal
            icon='cross'
            onClick={() => {
              onClose();
            }}/>
        </div>
        <div className='bp5-dialog-body'>
          <FormGroup
            labelFor='exercise-package'
            label={t('exercises.package.name.title')}
          >
            <HTMLSelect
              large
              fill
              id='exercise-package'
              value={selectedPackageName}
              onChange={handlePackageChange}
            >
              <option className='hidden' value=''>{t('exercises.package.name.placeholder')}</option>
              {Object.keys(packagesWithVersions).map(packageName => (
                <option key={packageName} value={packageName}>
                  {packageName}
                </option>
              ))}
            </HTMLSelect>
          </FormGroup>
          {selectedPackageName && (
            <FormGroup
              labelFor='exercise-package-version'
              label={t('exercises.package.version.title')}
            >
              <HTMLSelect
                large
                fill
                id='exercise-package-version'
                value={selectedVersion}
                onChange={(event: React.ChangeEvent<HTMLSelectElement>) => {
                  setSelectedVersion(event.target.value);
                }}
              >
                <option value=''>{t('exercises.package.version.placeholder')}</option>
                {packagesWithVersions[selectedPackageName]?.map(version => (
                  <option key={version} value={version}>{version}</option>
                ))}
              </HTMLSelect>
            </FormGroup>
          )}
        </div>
        <div className='bp5-dialog-footer'>
          <div className='bp5-dialog-footer-actions'>
            <Button
              large
              intent='primary'
              text={t('common.add')}
              onClick={handleAddClick}
            />
          </div>
        </div>
      </Dialog>
    );
  }

  return null;
};

export default PackageDialog;
