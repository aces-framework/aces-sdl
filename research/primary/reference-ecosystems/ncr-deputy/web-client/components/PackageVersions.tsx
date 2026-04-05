import useSWR from 'swr';
import useTranslation from 'next-translate/useTranslation';
import { packageVersionsFetcher } from '../utils/api';
import Package from './Package';

const PackageVersions = ({ packageName }: { packageName: string }) => {
  const { t } = useTranslation('common');
  const { data: packageVersions, error: allPackageVersions } = useSWR(
    () => `/api/v1/package/${packageName}`,
    packageVersionsFetcher
  );

  if (!packageVersions) {
    return null;
  }

  if (allPackageVersions) {
    return <div>{t('failedLoadingPackages')} </div>;
  }

  return (
    <>
      {packageVersions.map((version) => (
        <Package
          key={`${packageName}-${version.version}`}
          version={version}
          deputyPackage={{ name: packageName }}
        />
      ))}
    </>
  );
};

export default PackageVersions;
