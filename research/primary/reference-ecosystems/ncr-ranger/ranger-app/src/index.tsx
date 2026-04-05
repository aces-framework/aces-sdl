
import React from 'react';
import ReactDOM from 'react-dom/client';
import {Provider} from 'react-redux';
import {ReactKeycloakProvider} from '@react-keycloak/web';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import store from './store';
// eslint-disable-next-line import/no-unassigned-import
import './i18n';
import keycloak from './keycloak';

const root = ReactDOM.createRoot(
  document.querySelector('#root')!,
);
root.render(
  <Provider store={store}>
    <ReactKeycloakProvider
      initOptions={{onLoad: 'login-required', checkLoginIframe: false}}
      authClient={keycloak}
    >
      <App/>
    </ReactKeycloakProvider>
  </Provider>,
);

reportWebVitals();
