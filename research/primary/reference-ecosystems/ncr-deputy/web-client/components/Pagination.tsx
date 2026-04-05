import { Button } from '@blueprintjs/core';

const Pagination = ({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) => {
  return (
    <div className="mt-[2rem] flex justify-center gap-8 items-center">
      <Button
        onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
        disabled={currentPage === 1}
        icon="chevron-left"
      />
      <span>
        {currentPage} / {totalPages}
      </span>
      <Button
        onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
        disabled={currentPage === totalPages}
        icon="chevron-right"
      />
    </div>
  );
};

export default Pagination;
