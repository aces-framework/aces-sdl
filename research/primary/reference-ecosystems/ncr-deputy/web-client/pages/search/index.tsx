import { GetServerSideProps } from 'next';
import SearchResults, { SearchProps } from '../../components/SearchResults';
import { DEFAULT_LIMIT, DEFAULT_PAGE } from '../../constants/constants';

const Search = ({
  currentPage,
  selectedLimit,
  q,
  type,
  categories,
}: SearchProps) => {
  return (
    <SearchResults
      currentPage={currentPage}
      selectedLimit={selectedLimit}
      q={q}
      type={type}
      categories={categories}
    />
  );
};

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { query } = context;
  const { page, limit, q, type, categories } = query;

  return {
    props: {
      currentPage: Number(page) || DEFAULT_PAGE,
      selectedLimit: Number(limit) || DEFAULT_LIMIT,
      q: q || '',
      type: type || '',
      categories: categories || '',
    },
  };
};

export default Search;
