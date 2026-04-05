import React from 'react';
import {Tag} from '@blueprintjs/core';
import type {DeploymentElement} from 'src/models/deployment';
import {DeployerType} from 'src/models/deployment';
import {useTranslation} from 'react-i18next';

const countNodesByType = (deploymentElements: DeploymentElement[]) => {
  let [virtualMachines, switches, templates, conditions, features, injects] = [0, 0, 0, 0, 0, 0];

  for (const element of deploymentElements) {
    switch (element.deployerType) {
      case (DeployerType.VirtualMachine): {
        virtualMachines += 1;
        break;
      }

      case (DeployerType.Switch): {
        switches += 1;
        break;
      }

      case (DeployerType.Template): {
        templates += 1;
        break;
      }

      case (DeployerType.Condition): {
        conditions += 1;
        break;
      }

      case (DeployerType.Feature): {
        features += 1;
        break;
      }

      case (DeployerType.Inject): {
        injects += 1;
        break;
      }

      default: {
        break;
      }
    }
  }

  return [virtualMachines, switches, templates, conditions, features, injects];
};

const InfoTag = ({name, count}: {name: string; count: number}) => (
  <div className='flex m-0.5 mt-auto mb-4'>
    <Tag>{name}: {count}</Tag>
  </div>
);

const InfoTags = (
  {deploymentElements}: {deploymentElements: DeploymentElement[]}) => {
  const [
    virtualMachineCount,
    switchCount,
    templateCount,
    _conditionCount,
    _featureCount,
    _injectCount,
  ] = countNodesByType(deploymentElements);
  const {t} = useTranslation();
  return (
    <div className='flex'>
      <InfoTag name={t('common.virtualMachines')} count={virtualMachineCount}/>
      <InfoTag name={t('common.switches')} count={switchCount}/>
      <InfoTag name={t('common.templates')} count={templateCount}/>
    </div>
  );
};

export default InfoTags;
