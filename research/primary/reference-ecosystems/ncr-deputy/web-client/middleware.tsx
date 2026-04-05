import validateQuery from 'middleware/validateQuery';
import { NextRequest, NextResponse } from 'next/server';

const clearSearchParams = (searchParams: URLSearchParams) => {
  searchParams.forEach((key) => {
    searchParams.delete(key);
  });
};

const setSearchParams = (
  searchParams: URLSearchParams,
  query: Record<string, any>
) => {
  Object.entries(query).forEach(([key, value]) => {
    searchParams.set(key, value);
  });
};

function middleware(req: NextRequest) {
  const { nextUrl } = req;
  const { pathname, searchParams } = nextUrl;

  const isApiOrNextPath =
    pathname.startsWith('/api/v1/') || pathname.startsWith('/_next');
  const isPackagesOrSearchPath =
    pathname.startsWith('/packages') || pathname.startsWith('/search');

  if (searchParams.toString() === '' || isApiOrNextPath) {
    return NextResponse.next();
  }

  if (isPackagesOrSearchPath) {
    const validatedQuery = validateQuery(searchParams);
    clearSearchParams(searchParams);
    setSearchParams(searchParams, validatedQuery);
  } else {
    clearSearchParams(searchParams);
  }

  return NextResponse.rewrite(nextUrl);
}

export default middleware;
