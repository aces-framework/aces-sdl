import type React from 'react';
import {Button} from '@blueprintjs/core';
import {type DeploymentElement} from 'src/models/deployment';
import {getElementStatusIntent} from 'src/utils/deploymentStatus';

type ChildStatusButtonProps = {
  childElement: DeploymentElement;
  selectedElement: DeploymentElement | undefined;
  setSelectedElement: (element: DeploymentElement) => void;
};

const ChildStatusButton: React.FC<ChildStatusButtonProps> = (
  {childElement, selectedElement, setSelectedElement},
) => (
  <div key={childElement.id}>
    <Button
      minimal
      fill
      outlined
      active={childElement.id === selectedElement?.id}
      className='border-2 rounded-xl outline-none'
      intent={getElementStatusIntent(childElement.status)}
      onClick={() => {
        setSelectedElement(childElement);
      }}
    >
      <div className='max-w-[8rem] font-bold text-base truncate'>
        {childElement?.scenarioReference}
      </div>
    </Button>
  </div>
);

export default ChildStatusButton;
