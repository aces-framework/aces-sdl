import { Session } from 'next-auth';

export interface Token {
  id: string;
  name: string;
  email: string;
  token: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export type TokenRest = Pick<Token, 'id' | 'name' | 'createdAt'>;

export type PostToken = Pick<Token, 'name' | 'email'>;

export type ModifiedSession = Session & {
  idToken?: string;
  refreshToken?: string;
};
