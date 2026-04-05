import {NonIdealState, Spinner} from '@blueprintjs/core';
import React from 'react';

const PageLoader = ({title}: {title: string}) => (
  <NonIdealState title={title}>
    <Spinner intent='primary' size={200}/>
  </NonIdealState>
);

export default PageLoader;
