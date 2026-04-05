export type Package = {
  id: string;
  name: string;
  description: string;
  readmeHtml: string;
  createdAt: string;
};

export type Version = {
  id: string;
  version: string;
  license: string;
  isYanked: boolean;
  readmePath: string;
  readmeHtml: string;
  packageSize: number;
  checksum: string;
  createdAt: string;
  updatedAt: string;
};

export type PackageWithVersions = {
  id: string;
  name: string;
  description: string;
  readmeHtml?: string;
  createdAt: string;
  versions: Version[];
};

export type PackagesWithVersionsAndPages = {
  packages: PackageWithVersions[];
  totalPages: number;
  totalPackages: number;
};

export type Category = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  deletedAt: string;
};
