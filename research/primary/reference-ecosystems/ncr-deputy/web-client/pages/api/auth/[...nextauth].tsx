import { NextApiRequest, NextApiResponse } from 'next';
import NextAuth, { AuthOptions } from 'next-auth';
import { JWT } from 'next-auth/jwt';
import { OAuthConfig } from 'next-auth/providers';
import KeycloakProvider, {
  KeycloakProfile,
} from 'next-auth/providers/keycloak';

export const refreshToken = async (token: JWT): Promise<JWT> => {
  try {
    const details = {
      client_id: process.env.KEYCLOAK_CLIENT_ID,
      client_secret: process.env.KEYCLOAK_CLIENT_SECRET,
      grant_type: ['refresh_token'],
      refresh_token: token.refreshToken,
    };
    const formBody: string[] = [];
    Object.entries(details).forEach(([key, value]: [string, any]) => {
      const encodedKey = encodeURIComponent(key);
      const encodedValue = encodeURIComponent(value);
      formBody.push(`${encodedKey}=${encodedValue}`);
    });
    const formData = formBody.join('&');
    const url = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      },
      body: formData,
    });
    const refreshedTokens = await response.json();
    if (!response.ok) throw refreshedTokens;
    return {
      ...token,
      idToken: refreshedTokens.id_token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpired: Date.now() + (refreshedTokens.expires_in - 15) * 1000,
      refreshToken: refreshedTokens.refresh_token,
      refreshTokenExpired:
        Date.now() + (refreshedTokens.refresh_expires_in - 15) * 1000,
    };
  } catch (error) {
    return {
      ...token,
      error: 'RefreshAccessTokenError',
    };
  }
};

export const authOptions: AuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_CLIENT_ID ?? '',
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? '',
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
  ],
  session: {
    strategy: 'jwt',
  },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        // eslint-disable-next-line no-param-reassign
        token.accessToken = account.access_token;
        // eslint-disable-next-line no-param-reassign
        token.refreshToken = account.refresh_token;
        return token;
      }
      return refreshToken(token);
    },
    async session({ session, token }) {
      // eslint-disable-next-line no-param-reassign
      session.accessToken = token.accessToken as string;
      // eslint-disable-next-line no-param-reassign
      session.refreshToken = token.refreshToken as string;

      if (token.error) {
        // eslint-disable-next-line no-param-reassign
        session.error = token.error as string;
      }

      return session;
    },
  },
  events: {
    async signOut({ token }: { token: JWT }) {
      const issuerUrl = (
        authOptions.providers.find(
          (p) => p.id === 'keycloak'
        ) as OAuthConfig<KeycloakProfile>
      ).options!.issuer!;

      const logOutUrl = new URL(`${issuerUrl}/protocol/openid-connect/logout`);
      logOutUrl.searchParams.set('id_token_hint', token.idToken! as string);

      const response = await fetch(logOutUrl);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to log out: ${response.statusText} - ${errorText}`
        );
      }
    },
  },
};

export default (req: NextApiRequest, res: NextApiResponse) => {
  res.setHeader(
    'Cache-Control',
    'no-store, no-cache, must-revalidate, proxy-revalidate, private'
  );
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  res.setHeader('Surrogate-Control', 'no-store');

  return NextAuth(req, res, authOptions);
};
