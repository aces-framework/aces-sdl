/* eslint-disable import/prefer-default-export */
import semverCompare from 'semver-compare';
import { Category, Version } from '../interfaces/Package';

export const compareVersions = (a: Version, b: Version) =>
  semverCompare(a.version, b.version);

export const compareCategories = (a: Category, b: Category) =>
  a.name.localeCompare(b.name);
