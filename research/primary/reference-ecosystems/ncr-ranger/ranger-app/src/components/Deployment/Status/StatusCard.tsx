import React from 'react';
import {
  Button,
  Intent,
  Collapse,
  H4,
  Colors,
  ButtonGroup,
} from '@blueprintjs/core';
import {sortByProperty} from 'sort-by-property';
import {
  type DeploymentElement,
  DeployerType,
  ElementStatus,
} from 'src/models/deployment';
import {getElementStatusIntent} from 'src/utils/deploymentStatus';
import {useTranslation} from 'react-i18next';
import ChildStatusButton from './ChildStatusButton';

const StatusCard = ({element, childElements, selectedElement, setSelectedElement}:
{element: DeploymentElement; childElements: DeploymentElement[];
  selectedElement: DeploymentElement | undefined;
  setSelectedElement: (element: DeploymentElement) => void;}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const {t} = useTranslation();

  const handleToggle = () => {
    setSelectedElement(element);
    setIsOpen(!isOpen);
  };

  childElements.sort(sortByProperty('scenarioReference', 'asc'));

  const featureElements = childElements
    .filter(childElement => childElement.deployerType === DeployerType.Feature);
  const injectElements = childElements
    .filter(childElement => childElement.deployerType === DeployerType.Inject);
  const conditionElements = childElements
    .filter(childElement => childElement.deployerType === DeployerType.Condition);

  const hasFailedChild = childElements.some(
    child => child.status === (ElementStatus.Failed || ElementStatus.RemoveFailed));
  const isChildElementSelected = element.handlerReference ? element.handlerReference
    === selectedElement?.parentNodeId : false;

  return (
    <div>
      <div className='m-4'>
        <ButtonGroup className='flex w-full'>
          <Button
            minimal
            fill
            outlined
            active={element.id === selectedElement?.id || isChildElementSelected}
            color={element.id === selectedElement?.id ? Colors.BLUE3 : ''}
            className='w-full rounded-xl outline-none'
            intent={hasFailedChild ? Intent.DANGER
              : getElementStatusIntent(element.status)}
            onClick={() => {
              setSelectedElement(element);
            }}
          >
            <span className='font-bold text-xl'>
              {element?.scenarioReference}
            </span>
          </Button>
          {childElements.length > 0 && element.status !== ElementStatus.Ongoing
          && (
            <Button
              minimal
              outlined
              className='flex rounded-xl outline-none'
              intent={hasFailedChild ? Intent.DANGER
                : getElementStatusIntent(element.status)}
              icon={isOpen ? 'chevron-up' : 'chevron-down'}
              onClick={handleToggle}
            > {isOpen ? t('common.collapse') : t('common.expand')}
            </Button>
          )}
        </ButtonGroup>
        {childElements.length > 0 && (
          <Collapse isOpen={isOpen}>
            <div className='grid grid-cols-6 gap-3 mb-4 p-4 border-2 border-t-0 rounded-xl'>
              {featureElements.length > 0 && (
                <>
                  <H4 className='col-span-6 text-center'>
                    {t('deployments.deployerTypes.features')}
                  </H4>
                  {featureElements.map(childElement => (
                    <ChildStatusButton
                      key={childElement.id}
                      childElement={childElement}
                      selectedElement={selectedElement}
                      setSelectedElement={setSelectedElement}
                    />
                  ))}
                </>
              )}
              {conditionElements.length > 0 && (
                <>
                  <H4 className='col-span-6 text-center'>
                    {t('deployments.deployerTypes.conditions')}
                  </H4>
                  {conditionElements.map(childElement => (
                    <ChildStatusButton
                      key={childElement.id}
                      childElement={childElement}
                      selectedElement={selectedElement}
                      setSelectedElement={setSelectedElement}
                    />
                  ))}
                </>
              )}
              {injectElements.length > 0 && (
                <>
                  <H4 className='col-span-6 text-center'>
                    {t('deployments.deployerTypes.injects')}
                  </H4>
                  {injectElements.map(childElement => (
                    <ChildStatusButton
                      key={childElement.id}
                      childElement={childElement}
                      selectedElement={selectedElement}
                      setSelectedElement={setSelectedElement}
                    />
                  ))}
                </>
              )}
            </div>
          </Collapse>
        )}
      </div>
    </div>
  );
};

export default StatusCard;
