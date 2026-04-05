import useSWR from 'swr';
import useTranslation from 'next-translate/useTranslation';
import { H2 } from '@blueprintjs/core';
import { categoryFetcher } from '../utils/api';
import PackageCategories from './PackageCategories';

const CategoryListView = () => {
  const { t } = useTranslation('common');
  const { data: categories, error } = useSWR(
    `/api/v1/category`,
    categoryFetcher
  );

  if (error || !categories || categories.length === 0) {
    return <div>{t('failedLoadingCategories')}</div>;
  }

  return (
    <div className="lg:max-w-[60rem] max-w-[80%]">
      <H2 className="mt-[1rem]">{t('categories')}</H2>
      <PackageCategories
        packageCategories={categories.map((category) => category.name)}
      />
    </div>
  );
};

export default CategoryListView;
