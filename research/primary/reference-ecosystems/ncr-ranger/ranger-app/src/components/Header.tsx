import React, {useState} from 'react';
import {Button, H2} from '@blueprintjs/core';

// eslint-disable-next-line @typescript-eslint/comma-dangle
const Header = <T,>(
  {onSubmit, buttonTitle, headerTitle, children}: {
    onSubmit: (value: T) => void;
    buttonTitle: string;
    headerTitle: string;
    children?: React.ReactElement<{
      onCancel: () => void;
      onSubmit: (value: T) => void;
      title: string;
      isOpen: boolean;
    }, any>;
  },
) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <div className='flex flex-row justify-between mb-16'>
        <H2>{headerTitle}</H2>
        {children && (
          <Button
            large
            icon='add'
            intent='success'
            text={buttonTitle}
            onClick={() => {
              setIsOpen(true);
            }}/>
        )}
      </div>

      {children && React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React
            .cloneElement(child, {
              isOpen,
              onCancel() {
                setIsOpen(false);
              },
              onSubmit(value: T) {
                setIsOpen(false);
                onSubmit(value);
              },
            });
        }

        return null;
      })}
    </>
  );
};

export default Header;
