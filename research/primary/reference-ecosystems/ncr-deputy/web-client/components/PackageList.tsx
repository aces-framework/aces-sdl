import { getLatestVersion } from '../utils';
import { PackageWithVersions } from '../interfaces/Package';
import Package from './Package';

const PackageList = ({ packages }: { packages: PackageWithVersions[] }) => {
  return (
    <>
      {packages.map((deputyPackage) => {
        const latestVersion = getLatestVersion(deputyPackage);
        return (
          latestVersion && (
            <Package
              key={`${deputyPackage.name}-${latestVersion.version}`}
              deputyPackage={deputyPackage}
              version={latestVersion}
            />
          )
        );
      })}
    </>
  );
};

export default PackageList;
