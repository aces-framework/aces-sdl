import { PackageWithVersions, Version } from '../interfaces/Package';

export const getLatestVersion = (pkg: PackageWithVersions): Version | null => {
  if (pkg.versions.length > 0) {
    return pkg.versions[pkg.versions.length - 1];
  }

  return null;
};

export const displayLocalTime = (iso8601Date: string): string => {
  const date = new Date(iso8601Date);
  return date.toLocaleString();
};

export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${(bytes / k ** i).toFixed(dm)} ${sizes[i]}`;
}

export function extractAndRemoveTypeAndCategory(inputString: string): {
  type: string | null;
  categories: string | null;
  remainingString: string;
} {
  const typeRegex = /type:(\w+)/;
  const categoryRegex = /categories:([^ ]+)/;
  let remainingString = inputString;
  let type: string | null = null;
  let categories: string | null = null;

  const matchType = inputString.match(typeRegex);
  if (matchType) {
    [, type] = matchType;
    remainingString = remainingString.replace(typeRegex, '').trim();
  }

  const matchCategory = inputString.match(categoryRegex);
  if (matchCategory) {
    [, categories] = matchCategory;
    remainingString = remainingString.replace(categoryRegex, '').trim();
  }
  return { type, categories, remainingString };
}

export const calculateStartEndIndex = (
  currentPage: number,
  selectedLimit: number,
  totalCount: number
) => {
  const startIndex = (currentPage - 1) * selectedLimit + 1;
  const endIndex = Math.min(startIndex + selectedLimit - 1, totalCount);
  return { startIndex, endIndex };
};

export function getEncodedSearchUrl(searchInput: string) {
  const parsedSearchInput = extractAndRemoveTypeAndCategory(searchInput);

  let searchUrl = `/search?q=${encodeURIComponent(
    parsedSearchInput.remainingString
  )}`;
  if (parsedSearchInput.type) {
    if (searchUrl) {
      searchUrl += `&type=${encodeURIComponent(parsedSearchInput.type)}`;
    }
  }
  if (parsedSearchInput.categories) {
    if (searchUrl) {
      searchUrl += `&categories=${encodeURIComponent(
        parsedSearchInput.categories
      )}`;
    }
  }
  return searchUrl;
}

export function getSearchUrlAndInput(
  q: string,
  currentPage: number,
  selectedLimit: number,
  type: string,
  categories: string
) {
  let apiSearchUrl = `/api/v1/package?search_term=${q}&page=${currentPage}&limit=${selectedLimit}`;
  let searchInput = `"${q}"`;
  if (type) {
    apiSearchUrl += `&type=${type}`;
    searchInput += ` (type: ${type})`;
  }
  if (categories) {
    apiSearchUrl += `&categories=${categories}`;
    searchInput += ` (categories: ${categories})`;
  }
  return { apiSearchUrl, searchInput };
}
