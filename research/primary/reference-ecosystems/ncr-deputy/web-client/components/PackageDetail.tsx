import { ParsedUrlQuery } from 'querystring';
import useSWR from 'swr';
import { Card, Elevation, H2, Tag } from '@blueprintjs/core';
import useTranslation from 'next-translate/useTranslation';
import { useRouter } from 'next/router';
import { TabList, TabPanel, Tab, Tabs } from 'react-tabs';
import 'react-tabs/style/react-tabs.css';
import { packageTOMLFetcher, packageVersionFetcher } from '../utils/api';
import PackageVersions from './PackageVersions';
import FilePreview from './FilePreview';
import { displayLocalTime, formatBytes } from '../utils';
import PackageCategories from './PackageCategories';
import VersionTag from './Versiontag';
import ContentIFrame from './ContentIFrame';

interface DetailParams extends ParsedUrlQuery {
  name: string;
  version: string;
}

const PackageDetailView = () => {
  const { t } = useTranslation('common');
  const { query } = useRouter();
  const { name, version } = query as DetailParams;

  const { data: latestVersion, error: latestVersionError } = useSWR(
    `/api/v1/package/${name}/${version}?include_readme=true`,
    packageVersionFetcher
  );

  const { data: packageToml, error: packageTOMLError } = useSWR(
    `/api/v1/package/${name}/${version}/path/package.toml`,
    packageTOMLFetcher
  );

  if (!latestVersion || !packageToml) {
    return null;
  }

  if (latestVersionError || packageTOMLError) {
    return <div>{t('failedLoadingPackages')} </div>;
  }

  return (
    <Card
      className="mt-[1rem] xl:w-[60rem] w-full m-[2rem]"
      interactive={false}
      elevation={Elevation.ONE}
    >
      <div className="flex justify-between">
        <H2 className="m-[1rem]">{name}</H2>
        <div className="flex flex-col gap-4">
          <div className="flex justify-end">
            <Tag minimal large round>
              {t('createdAt')}: {displayLocalTime(latestVersion.createdAt)}
            </Tag>
          </div>
          <div className="flex gap-4">
            <VersionTag intent="primary" version={latestVersion.version} />
            <Tag icon="list-columns" large minimal round intent="primary">
              {packageToml.content.type.toUpperCase()}
            </Tag>
            <Tag icon="briefcase" large minimal round intent="primary">
              {latestVersion.license}
            </Tag>
            <Tag icon="database" large minimal round intent="primary">
              {formatBytes(latestVersion.packageSize)}
            </Tag>
            {latestVersion.isYanked && (
              <Tag large minimal round intent="danger">
                {t('yanked')}
              </Tag>
            )}
          </div>
        </div>
      </div>
      <Tabs className="pt-[2rem] pb-[2rem]">
        <TabList>
          <Tab>Readme</Tab>
          <Tab>{t('versions')}</Tab>
          <Tab
            disabled={
              !packageToml?.package?.categories?.some((category) => category)
            }
          >
            {t('categories')}
          </Tab>
          <Tab
            disabled={!packageToml.content.preview || latestVersion.isYanked}
          >
            {t('preview')}
          </Tab>
        </TabList>

        <TabPanel>
          <div className="mt-[2rem]">
            <ContentIFrame content={latestVersion.readmeHtml} />
          </div>
        </TabPanel>
        <TabPanel>
          <PackageVersions packageName={name} />
        </TabPanel>
        <TabPanel>
          <PackageCategories
            packageCategories={packageToml.package.categories}
          />
        </TabPanel>
        <TabPanel>
          <FilePreview
            packageData={packageToml}
            isYanked={latestVersion.isYanked}
          />
        </TabPanel>
      </Tabs>
    </Card>
  );
};

export default PackageDetailView;
