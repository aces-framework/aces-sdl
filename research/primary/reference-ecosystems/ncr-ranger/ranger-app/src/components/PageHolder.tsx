import type {ReactNode} from 'react';
import React from 'react';

const PageHolder = ({children}: {children: ReactNode}) => (
  <div className='flex justify-center'>
    <div className='pt-8 max-w-4xl w-full'>
      {children}
    </div>
  </div>
);

export default PageHolder;
