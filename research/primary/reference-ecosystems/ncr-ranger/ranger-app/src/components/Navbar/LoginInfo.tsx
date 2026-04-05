import React from 'react';
import {Alignment, Button, Navbar} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import {useKeycloak} from '@react-keycloak/web';
import RoleSelect from './RoleSelect';

const LoginInfo = () => {
  const {t} = useTranslation();
  const {keycloak} = useKeycloak();

  return (
    <Navbar.Group align={Alignment.RIGHT}>
      {keycloak.authenticated && (
        <>
          {keycloak.tokenParsed?.preferred_username !== undefined && (
            <Navbar.Heading className='hidden md:block'>

              {t('menu.greeting',
                {
                  username: keycloak
                    .tokenParsed?.preferred_username as string,
                })}
            </Navbar.Heading>
          )}
          <Navbar.Heading>
            <RoleSelect keycloak={keycloak}/>
          </Navbar.Heading>
          <Button
            minimal
            icon='log-out'
            onClick={async () => keycloak.logout()}
          >{t('menu.logout')}
          </Button>
        </>
      )}
    </Navbar.Group>
  );
};

export default LoginInfo;
