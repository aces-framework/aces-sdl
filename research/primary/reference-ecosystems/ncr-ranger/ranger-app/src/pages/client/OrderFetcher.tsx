import React from 'react';
import {useTranslation} from 'react-i18next';
import {useParams} from 'react-router-dom';
import {type OrderDetailRouteParamaters} from 'src/models/routes';
import PageLoader from 'src/components/PageLoader';
import useDefaultRoleSelect from 'src/hooks/useDefaultRoleSelect';
import {skipToken} from '@reduxjs/toolkit/query';
import {useClientGetOrderQuery} from 'src/slices/apiSlice';
import OrderDetail from './OrderDetail';

const ClientOrderFetcher = () => {
  const {t} = useTranslation();
  const {orderId, stage} = useParams<OrderDetailRouteParamaters>();
  const userRole = useDefaultRoleSelect();
  const {data: order, isLoading} = useClientGetOrderQuery(orderId ?? skipToken);

  if (isLoading) {
    return (
      <PageLoader title={t('orders.loadingOrder')}/>
    );
  }

  return (<OrderDetail order={order} userRole={userRole} stage={stage}/>);
};

export default ClientOrderFetcher;
