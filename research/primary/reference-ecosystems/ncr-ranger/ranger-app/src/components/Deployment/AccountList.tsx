import React from 'react';
import {useTranslation} from 'react-i18next';
import {Callout, Button, Card, Elevation} from '@blueprintjs/core';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import {getElementNameById} from 'src/utils';
import {type DeploymentElement} from 'src/models/deployment';
import {type AdUser} from 'src/models/groups';

const AccountList = ({users, deploymentElements}:
{users: AdUser[] | undefined;
  deploymentElements: DeploymentElement[] | undefined;
}) => {
  const {t} = useTranslation();
  const sortedElements = deploymentElements?.slice()
    .sort((a, b) => a.scenarioReference.localeCompare(b.scenarioReference));

  if (users && users.length > 0) {
    return (
      <Card className='text-center p-0 rounded-xl overflow-hidden' elevation={Elevation.TWO}>
        <table className='w-full'>
          <thead className='text-base border-b bg-slate-200'>
            <tr>
              <th className='py-4' rowSpan={2}>{t('accountsTable.vmName')}</th>
            </tr>
            <tr className='flex'>
              <th className='py-4 w-1/3'>{t('accountsTable.username')}</th>
              <th className='py-4 w-1/3 border-x'>{t('accountsTable.password')}</th>
              <th className='py-4 w-1/3'>{t('accountsTable.privatekey')}</th>
            </tr>

          </thead>
          <tbody className='text-center'>
            {users.map(adUser => (
              <tr key={adUser.vmId} className='border-t border even:bg-slate-100'>
                <td className='my-4 border-r'>
                  {getElementNameById(sortedElements ?? [], adUser.vmId) ?? adUser.vmId}
                </td>
                <td colSpan={4}>
                  <table className='w-full h-full'>
                    <tbody>
                      {adUser.accounts.map(account => (
                        <tr
                          key={account.id}
                          className='w-full even:bg-slate-200 overflow-auto'
                        >
                          <td className='py-3 w-1/3 overflow-auto'>{account.username}</td>
                          <td className='py-3 w-1/3 border-x overflow-auto'>
                            {account.password}
                          </td>
                          <td className='py-3 w-1/3'>
                            <Button
                              icon='clipboard'
                              disabled={!account.privateKey}
                              onClick={async () => {
                                try {
                                  await navigator.clipboard
                                    .writeText(account.privateKey ?? '');
                                  toastSuccess(t('accountsTable.copySuccess'));
                                } catch (error) {
                                  toastWarning(
                                    t('accountsTable.copyFail', {errorMessage: error}));
                                }
                              }}
                            >
                              {t('accountsTable.copyButton')}
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    );
  }

  return (
    <Callout title={t('deployments.noAccounts') ?? ''}/>
  );
};

export default AccountList;
