// This file can be replaced during build by using the `fileReplacements` array.
// `ng build --configuration production` replaces `environment.ts` with `environment.prod.ts`.
// The list of file replacements can be found in `angular.json`.

// OIDC url
const OIDC_URL = 'https://172.19.0.22';
// backend url
const API_URL = 'https://172.19.0.22';
// frontend home url
const HOME_URL = 'https://localhost:4200';

export const environment = {
    production: true,
    modelSimulatorConfig: {
        adaptiveBasePath: API_URL + '/adaptive-training/api/v1/',
    },
    authConfig: {
        guardMainPageRedirect: 'home',
        guardLoginPageRedirect: 'login',
        interceptorAllowedUrls: [OIDC_URL, API_URL],
        authorizationStrategyConfig: {
            authorizationUrl: API_URL + '/user-and-group/api/v1/users/info',
        },
        providers: [
            {
                label: 'Login with local Keycloak',
                textColor: 'white',
                backgroundColor: '#1e2173',
                oidcConfig: {
                    requireHttps: true,
                    clearHashAfterLogin: true,
                    issuer: OIDC_URL + '/keycloak/realms/CRCZP',
                    clientId: 'CRCZP-client',
                    redirectUri: HOME_URL,
                    scope: 'openid email profile offline_access',
                    logoutUrl: OIDC_URL + '/keycloak/realms/CRCZP/protocol/openid-connect/logout',
                    silentRefreshRedirectUri: HOME_URL + '/silent-refresh.html',
                    postLogoutRedirectUri: HOME_URL + '/logout-confirmed',
                },
            },
        ],
    },
};
