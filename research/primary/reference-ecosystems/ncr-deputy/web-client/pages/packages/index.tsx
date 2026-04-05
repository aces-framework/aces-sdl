import { GetServerSideProps } from 'next';
import PackageListView, {
  PackageListViewProps,
} from '../../components/PackageListView';
import { DEFAULT_LIMIT, DEFAULT_PAGE } from '../../constants/constants';

const Packages = ({ currentPage, selectedLimit }: PackageListViewProps) => {
  return (
    <PackageListView currentPage={currentPage} selectedLimit={selectedLimit} />
  );
};

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { page, limit } = context.query;

  return {
    props: {
      currentPage: Number(page) || DEFAULT_PAGE,
      selectedLimit: Number(limit) || DEFAULT_LIMIT,
    },
  };
};

export default Packages;
