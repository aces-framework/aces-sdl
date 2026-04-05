import {Callout, H5, Icon} from '@blueprintjs/core';
import {useKeycloak} from '@react-keycloak/web';
import humanInterval from 'human-interval';
import React from 'react';
import {useTranslation} from 'react-i18next';
import Header from 'src/components/Header';
import {
  useClientAddOrderMutation,
  useClientGetOrdersQuery,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import {OrderStatus} from 'src/models/order';
import OrderCard from './Card';
import NameDialog from './NameDialog';

const OrderList = () => {
  const {
    data: potentialOrders,
  } = useClientGetOrdersQuery(
    undefined,
    {pollingInterval: humanInterval('5 seconds')},
  );
  const orders = potentialOrders?.slice().sort(sortByProperty('createdAt', 'desc'));
  const {t} = useTranslation();
  const [addOrder, _newOrder] = useClientAddOrderMutation();
  const {keycloak} = useKeycloak();

  return (
    <>
      <Header
        headerTitle={t('orders.title')}
        buttonTitle={t('orders.createOrder')}
        onSubmit={async (name: string) => {
          const userInfo = await keycloak.loadUserInfo() as {email?: string};
          if (userInfo.email) {
            await addOrder({
              name,
              clientId: userInfo.email,
              status: OrderStatus.DRAFT,
            });
          }
        }}
      >
        <NameDialog
          title={t('orders.newOrder')}
        />
      </Header>
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
