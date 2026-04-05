import { H4 } from '@blueprintjs/core';
import Link from 'next/link';

const PackageCategories = ({
  packageCategories,
}: {
  packageCategories: string[] | undefined;
}) => {
  if (!packageCategories) {
    return null;
  }

  return (
    <div className="grid gap-4 grid-cols-3 mt-[2rem]">
      {packageCategories
        .filter((category) => category.trim() !== '')
        .sort()
        .map((category) => (
          <Link
            className="bp5-button bp5-large bp5-intent-primary"
            key={category}
            href={`/search?q=&categories=${category}`}
          >
            <H4 className="m-0 text-cr14-gray truncate max-w-[100%]">
              {category}
            </H4>
          </Link>
        ))}
    </div>
  );
};

export default PackageCategories;
