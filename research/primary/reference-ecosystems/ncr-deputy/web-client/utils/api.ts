import { Fetcher } from 'swr';
import TOML from '@iarna/toml';
import { getSession } from 'next-auth/react';
import {
  Category,
  Package,
  PackagesWithVersionsAndPages,
  Version,
} from '../interfaces/Package';
import { Project } from '../interfaces/Project';
import {
  ModifiedSession,
  PostToken,
  Token,
  TokenRest,
} from '../interfaces/Token';

import { compareCategories, compareVersions } from './sort';

export const packageFetcher: Fetcher<Package[], string> = async (...url) => {
  const response = await fetch(...url);
  return response.json();
};

export const packagesWithVersionsFetcher: Fetcher<
  PackagesWithVersionsAndPages,
  string
> = async (...url) => {
  const packagesWithVersionsAndPages: PackagesWithVersionsAndPages =
    await fetch(...url).then(async (res) => res.json());

  packagesWithVersionsAndPages.packages.map((pkg) => {
    return pkg.versions.sort(compareVersions);
  });

  return packagesWithVersionsAndPages;
};

export const packageVersionsFetcher: Fetcher<Version[], string> = async (
  ...url
) => {
  const response = await fetch(...url);
  const versions: Version[] = await response.json();
  return versions.sort(compareVersions).reverse();
};

export const packageVersionFetcher: Fetcher<Version, string> = async (
  ...url
) => {
  const response = await fetch(...url);
  return response.json();
};

export const packageTOMLFetcher: Fetcher<Project, string> = async (...url) => {
  const response = await fetch(...url);
  return TOML.parse(await response.text()) as unknown as Project;
};

export const categoryFetcher: Fetcher<Category[], string> = async (...url) => {
  const response = await fetch(...url);
  const categories: Category[] = await response.json();
  return categories.sort(compareCategories);
};

export const apiTokenFetcher: Fetcher<TokenRest[], string> = async (...url) => {
  const session = (await getSession()) as ModifiedSession;
  if (session && session.accessToken) {
    const response = await fetch(...url, {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });
    return response.json();
  }

  throw new Error('No session found');
};

export const createToken = async (postToken: PostToken) => {
  const session = (await getSession()) as ModifiedSession;
  if (session && session.accessToken) {
    const response = await fetch('/api/v1/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.accessToken}`,
      },
      body: JSON.stringify(postToken),
    });

    if (response.ok) {
      return (await response.json()) as unknown as Token;
    }

    throw new Error('Failed to create token');
  }

  throw new Error('No session found');
};

export const deleteToken = async (tokenId: String) => {
  const session = (await getSession()) as ModifiedSession;
  if (session && session.accessToken) {
    const response = await fetch(`/api/v1/token/${tokenId}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    if (response.ok) {
      return;
    }

    throw new Error('Failed to delete token');
  }

  throw new Error('No session found');
};
