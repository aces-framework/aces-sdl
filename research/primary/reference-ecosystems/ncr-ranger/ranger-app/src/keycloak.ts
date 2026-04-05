
import Keycloak from 'keycloak-js';

/* eslint-disable @typescript-eslint/no-unsafe-assignment */
const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});
/* eslint-enable @typescript-eslint/no-unsafe-assignment */

export default keycloak;
