import { Card, Elevation, Tag } from '@blueprintjs/core';
import useTranslation from 'next-translate/useTranslation';
import { useRouter } from 'next/router';
import { Version } from '../interfaces/Package';
import { formatBytes } from '../utils';
import VersionTag from './Versiontag';

const Package = ({
  deputyPackage,
  version,
}: {
  deputyPackage: {
    name: string;
    description?: string;
  };
  version: Version;
}) => {
  const { t } = useTranslation('common');
  const router = useRouter();
  return (
    <Card
      key={`${deputyPackage.name}-${version.version}`}
      interactive
      elevation={Elevation.TWO}
      onClick={() =>
        router.push(`/packages/${deputyPackage.name}/${version.version}`)
      }
      className="mt-[2rem] rounded-xl"
    >
      <div className="flex flex-col gap-8">
        <div className="flex justify-between items-end">
          <span className="decoration-0 font-bold text-xl text-nowrap text-[#0082be]">
            {deputyPackage.name}
          </span>
          <div className="flex gap-4">
            {version.packageSize > 0 && (
              <Tag large minimal round icon="database">
                {formatBytes(version.packageSize)}
              </Tag>
            )}
            <VersionTag version={version.version} />
            {version.isYanked && (
              <Tag large minimal round intent="danger">
                {t('yanked')}
              </Tag>
            )}
          </div>
        </div>
        <div>{deputyPackage.description}</div>
      </div>
    </Card>
  );
};

export default Package;
