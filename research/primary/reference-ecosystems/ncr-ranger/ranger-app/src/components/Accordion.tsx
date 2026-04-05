import React, {type ReactNode} from 'react';
import {Collapse, Button} from '@blueprintjs/core';

export type AccordionProps = {
  title: string;
  children: ReactNode;
  isOpen?: boolean;
  onToggle?: (isOpen: boolean) => void;
  className?: string;
};

const Accordion = ({title, children, isOpen = false, onToggle, className}: AccordionProps) => {
  const handleToggle = () => {
    if (onToggle) {
      onToggle(!isOpen);
    }
  };

  return (
    <div className={className}>
      <Button minimal fill onClick={handleToggle}>
        <span className='font-bold align-middle text-xl'>{title}</span>
      </Button>
      <Collapse isOpen={isOpen}>{children}</Collapse>
    </div>
  );
};

export default Accordion;
