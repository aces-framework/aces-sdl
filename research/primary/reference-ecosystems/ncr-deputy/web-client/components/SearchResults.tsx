import { ChangeEvent } from 'react';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import useTranslation from 'next-translate/useTranslation';
import { H4 } from '@blueprintjs/core';
import { packagesWithVersionsFetcher } from '../utils/api';
import { calculateStartEndIndex, getSearchUrlAndInput } from '../utils';
import PageLimitSelect from './PageLimitSelect';
import Pagination from './Pagination';
import PackageList from './PackageList';

export interface SearchProps {
  currentPage: number;
  selectedLimit: number;
  q: string;
  type: string;
  categories: string;
}

const SearchResults = ({
  q,
  currentPage,
  selectedLimit,
  type,
  categories,
}: SearchProps) => {
  const { t } = useTranslation('common');
  const router = useRouter();

  const { apiSearchUrl, searchInput } = getSearchUrlAndInput(
    q,
    currentPage,
    selectedLimit,
    type,
    categories
  );

  const { data: searchResults, error } = useSWR(
    `${apiSearchUrl}`,
    packagesWithVersionsFetcher
  );

  if (error) {
    return (
      <div className="w-[80%] max-w-[60rem] mt-[2rem]">
        <H4>{t('searchResultsFor', { searchInput })}</H4>
        <div>{t('failedLoadingPackages')}</div>
      </div>
    );
  }

  if (!searchResults) {
    return null;
  }

  const { startIndex, endIndex } = calculateStartEndIndex(
    currentPage,
    selectedLimit,
    searchResults.totalPackages
  );

  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const newLimit = parseInt(event.target.value, 10);
    router.push({
      pathname: router.pathname,
      query: { ...router.query, page: 1, limit: newLimit },
    });
  };

  const handlePageChange = (newPage: number) => {
    router.push({
      pathname: router.pathname,
      query: { ...router.query, page: newPage },
    });
  };

  return (
    <div className="w-[80%] max-w-[60rem] mt-[2rem]">
      <H4>{t('searchResultsFor', { searchInput })}</H4>
      {searchResults.packages.length === 0 && <div>{t('noResults')}</div>}
      {searchResults.packages.length > 0 && (
        <>
          <div className="flex justify-between mt-[2rem]">
            <PageLimitSelect
              selectedLimit={selectedLimit}
              onChange={handleLimitChange}
            />
            <span>
              {t('resultsCount', {
                startIndex,
                endIndex,
                count: searchResults.totalPackages,
              })}
            </span>
          </div>

          <PackageList packages={searchResults.packages} />

          <Pagination
            currentPage={currentPage}
            totalPages={searchResults.totalPages}
            onPageChange={handlePageChange}
          />
        </>
      )}
    </div>
  );
};

export default SearchResults;
