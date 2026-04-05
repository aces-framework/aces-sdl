import React, {useEffect, useState} from 'react';
import {DeployerType, type DeploymentElement} from 'src/models/deployment';
import {
  Button,
  Collapse,
  Divider,
  H3,
  H4,
  Pre,
} from '@blueprintjs/core';
import {sortByProperty} from 'sort-by-property';
import {getReadableDeployerType, getReadableElementStatus} from 'src/utils';
import {useTranslation} from 'react-i18next';
import StatusCard from './StatusCard';

const StatusBox = (
  {deploymentElements}: {deploymentElements: DeploymentElement[]}) => {
  const {t} = useTranslation();
  const [selectedElement, setSelectedElement] = useState<DeploymentElement | undefined>(undefined);
  const [statusBoxOpen, setStatusBoxOpen] = useState(false);
  const [stdoutOpen, setStdoutOpen] = useState(false);
  const [stderrOpen, setStderrOpen] = useState(false);
  const [errorMessageOpen, setErrorMessageOpen] = useState(false);

  useEffect(() => {
    setStdoutOpen(false);
    setStderrOpen(false);
    setErrorMessageOpen(false);
  }, [selectedElement]);

  const sortedElements = deploymentElements.slice()
    .sort(sortByProperty('scenarioReference', 'asc'));

  const switchElements = sortedElements
    .filter(element => element.deployerType === DeployerType.Switch);
  const templateElements = sortedElements
    .filter(element => element.deployerType === DeployerType.Template);
  const virtualMachineElements = sortedElements
    .filter(element => element.deployerType === DeployerType.VirtualMachine);

  return (
    <div className='flex flex-col content-center items-center
      border-2 border-slate-400 rounded-xl relative'
    >
      <Button
        icon={statusBoxOpen ? 'chevron-up' : 'chevron-down'}
        className='h-6 text-base rounded-xl justify-center absolute -top-4 bg-blue-400 outline-none'
        onClick={() => {
          setStatusBoxOpen(!statusBoxOpen);
        }}
      >
        { statusBoxOpen ? t('deployments.status.hideStatusBox')
          : t('deployments.status.showStatusBox')}
      </Button>
      <Collapse className='w-full' isOpen={statusBoxOpen}>
        <div className='rounded-xl'>
          <H3 className='m-4'>{t('deployments.status.title')}</H3>

          {virtualMachineElements.length > 0 && (
            <div className='m-4 border-2 rounded-xl'>
              <H4 className='m-4'>{t('common.virtualMachines')}</H4>
              {virtualMachineElements.map(element => (
                <StatusCard
                  key={element.id}
                  element={element}
                  childElements={sortedElements
                    .filter(childElement => childElement.parentNodeId === element.handlerReference)}
                  selectedElement={selectedElement}
                  setSelectedElement={setSelectedElement}
                />
              ))}
            </div>
          )}

          {switchElements.length > 0 && (
            <div className='m-4 border-2 rounded-xl'>
              <H4 className='m-4'>{t('common.switches')}</H4>
              {switchElements.map(element => (
                <StatusCard
                  key={element.id}
                  element={element}
                  childElements={sortedElements
                    .filter(childElement => childElement.parentNodeId === element.handlerReference)}
                  selectedElement={selectedElement}
                  setSelectedElement={setSelectedElement}
                />
              ))}
            </div>
          )}

          {templateElements.length > 0 && (
            <div className='m-4 border-2 rounded-xl'>
              <H4 className='m-4'>{t('common.templates')}</H4>
              {templateElements.map(element => (
                <StatusCard
                  key={element.id}
                  element={element}
                  childElements={sortedElements
                    .filter(childElement => childElement.parentNodeId === element.handlerReference)}
                  selectedElement={selectedElement}
                  setSelectedElement={setSelectedElement}
                />
              ))}
            </div>
          )}
          {selectedElement && (
            <>
              <Divider className='m-4'/>
              <div className='m-4 p-4 border-2 rounded-xl overflow-auto'>
                <H4 className='mb-4'>{selectedElement.scenarioReference}</H4>
                <div className='flex flex-wrap'>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.handlerReference')}
                  </div>
                  <div className='w-1/2 mb-2'>{selectedElement.handlerReference}</div>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.type')}
                  </div>
                  <div className='w-1/2 mb-2'>
                    {getReadableDeployerType(t, selectedElement.deployerType)}
                  </div>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.status')}
                  </div>
                  <div className='w-1/2 mb-2'>
                    {getReadableElementStatus(t, selectedElement.status) }
                  </div>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.errorMessage')}
                  </div>
                  <div className='w-1/2 max-w-xs flex mb-2'>
                    <Button
                      className='flex-grow'
                      icon={errorMessageOpen ? 'chevron-up' : 'chevron-down'}
                      disabled={!selectedElement.errorMessage}
                      onClick={() => {
                        setErrorMessageOpen(!errorMessageOpen);
                      }}
                    >
                      {errorMessageOpen ? t('deployments.status.cardFields.hideErrorMessage')
                        : t('deployments.status.cardFields.showErrorMessage')}
                    </Button>
                  </div>
                  <div className='w-full'>
                    <Collapse isOpen={errorMessageOpen}>
                      <Pre className='overflow-auto'>{selectedElement.errorMessage}</Pre>
                    </Collapse>
                  </div>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.stdoutLogs')}
                  </div>
                  <div className='w-1/2 max-w-xs flex mb-2'>
                    <Button
                      className='flex-grow'
                      disabled={!selectedElement.executorStdout}
                      icon={stdoutOpen ? 'chevron-up' : 'chevron-down'}
                      onClick={() => {
                        setStdoutOpen(!stdoutOpen);
                      }}
                    >
                      {stdoutOpen ? t('deployments.status.cardFields.hideStdoutLogs')
                        : t('deployments.status.cardFields.showStdoutLogs')}
                    </Button>
                  </div>
                  <div className='w-full'>
                    <Collapse isOpen={stdoutOpen}>
                      <Pre className='overflow-auto'>{selectedElement.executorStdout}</Pre>
                    </Collapse>
                  </div>

                  <div className='w-1/2 font-bold'>
                    {t('deployments.status.cardFields.stderrLogs')}
                  </div>
                  <div className='w-1/2 max-w-xs flex mb-2'>
                    <Button
                      className='flex-grow'
                      icon={stderrOpen ? 'chevron-up' : 'chevron-down'}
                      disabled={!selectedElement.executorStderr}
                      onClick={() => {
                        setStderrOpen(!stderrOpen);
                      }}
                    >
                      {stderrOpen ? t('deployments.status.cardFields.hideStderrLogs')
                        : t('deployments.status.cardFields.showStderrLogs')}
                    </Button>
                  </div>
                  <div className='w-full'>
                    <Collapse isOpen={stderrOpen}>
                      <Pre className='overflow-auto'>{selectedElement.executorStderr}</Pre>
                    </Collapse>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </Collapse>
    </div>
  );
};

export default StatusBox;
