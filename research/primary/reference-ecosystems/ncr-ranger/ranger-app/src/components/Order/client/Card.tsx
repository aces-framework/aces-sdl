import type React from 'react';
import {Card, H2} from '@blueprintjs/core';
import {useNavigate} from 'react-router-dom';
import {type Order} from 'src/models/order';
import {useTranslation} from 'react-i18next';
import OrderStatusTag from './OrderStatusTag';

const OrderCard = ({order}: {order: Order}) => {
  const navigate = useNavigate();
  const {t} = useTranslation();

  return (
    <Card
      interactive
      elevation={2}
      onClick={() => {
        navigate(`/orders/${order.id}`);
      }}
    >
      <div className='flex flex-row justify-between'>
        <H2>{order.name}</H2>
        <OrderStatusTag order={order} t={t}/>
      </div>
    </Card>
  );
};

export default OrderCard;
