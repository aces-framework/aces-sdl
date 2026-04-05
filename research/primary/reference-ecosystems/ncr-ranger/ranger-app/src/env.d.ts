// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="vite/client" />

type ImportMetaEnv = {
  readonly VITE_KEYCLOAK_URL: string;
  readonly VITE_KEYCLOAK_REALM: string;
  readonly VITE_KEYCLOAK_CLIENT_ID: string;
};

  type ImportMeta = {
    readonly env: ImportMetaEnv;
  };
