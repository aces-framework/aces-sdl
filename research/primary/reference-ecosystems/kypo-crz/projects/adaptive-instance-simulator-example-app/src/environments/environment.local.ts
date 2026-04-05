// This file can be replaced during build by using the `fileReplacements` array.
// `ng build --configuration local` replaces `environment.ts` with `environment.local.ts`.
// The list of file replacements can be found in `angular.json`.

// OIDC url
const OIDC_URL = 'https://localhost:8080';
// backend url
const API_URL = 'http://localhost:3000';
// frontend home url
const HOME_URL = 'https://localhost:4200';

export const environment = {
    production: false,
    modelSimulatorConfig: {
        adaptiveBasePath: API_URL + '/adaptive-training/api/v1/',
    },
    authConfig: {
        guardMainPageRedirect: 'home',
        guardLoginPageRedirect: 'login',
        interceptorAllowedUrls: [OIDC_URL, API_URL, 'https://localhost', 'http://localhost'],
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

/*
 * In development mode, to ignore zone related error stack frames such as
 * `zone.run`, `zoneDelegate.invokeTask` for easier debugging, you can
 * import the following file, but please comment it out in production mode
 * because it will have performance impact when throw error
 */
// import 'zone.js/plugins/zone-error';  // Included with Angular CLI.
