import React, {type ReactNode, useState, Children, cloneElement} from 'react';
import Accordion, {type AccordionProps} from './Accordion';

type AccordionGroupProps = {
  children: ReactNode;
  className?: string;
};

type ClonedAccordionProps = AccordionProps & {
  isOpen: boolean;
  onToggle: (isOpen: boolean) => void;
};

const AccordionGroup = ({children, className}: AccordionGroupProps) => {
  const [openIndex, setOpenIndex] = useState<number>(-1);

  const handleAccordionToggle = (index: number, isOpen: boolean) => {
    setOpenIndex(isOpen ? index : -1);
  };

  return (
    <div className={className}>
      {Children.map(children, (child, index) => {
        if (React.isValidElement<AccordionProps>(child) && child.type === Accordion) {
          const clonedProps: ClonedAccordionProps = {
            ...child.props,
            isOpen: openIndex === index,
            onToggle(isOpen: boolean) {
              handleAccordionToggle(index, isOpen);
            },
          };
          return cloneElement(child, clonedProps);
        }

        return child;
      })}
    </div>
  );
};

export default AccordionGroup;
