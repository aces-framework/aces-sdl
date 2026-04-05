import {Callout, H2, H5, Icon} from '@blueprintjs/core';
import humanInterval from 'human-interval';
import React from 'react';
import {useTranslation} from 'react-i18next';
import {useAdminGetOrdersQuery} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import OrderCard from 'src/components/Order/client/Card';

const OrderList = () => {
  const {
    data: potentialOrders,
  } = useAdminGetOrdersQuery(
    undefined,
    {pollingInterval: humanInterval('5 seconds')},
  );
  const orders = potentialOrders?.slice().sort(sortByProperty('createdAt', 'desc'));
  const {t} = useTranslation();

  return (
    <>
      <H2 className='mb-16'>{t('orders.title')}</H2>
      {orders?.length === 0
      && (
        <Callout icon={null} className='my-8 flex items-center justify-between' intent='primary'>
          <div className='flex items-end'>
            <Icon icon='info-sign' className='mr-2'/>
            <H5 className='leading-[normal]'>{t('orders.noOrdersCallout')}</H5>
          </div>
        </Callout>)}
      <div className='flex flex-col gap-4'>
        {orders?.map(order => (
          <OrderCard key={order.id} order={order}/>
        ))}
      </div>
    </>
  );
};

export default OrderList;
