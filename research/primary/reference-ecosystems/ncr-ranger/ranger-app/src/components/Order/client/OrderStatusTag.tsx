import React from 'react';
import {Tag, type TagProps} from '@blueprintjs/core';
import {type TFunction} from 'i18next';
import {OrderStatus, type Order} from 'src/models/order';

const OrderStatusTag = ({order, t, tagProps}:
{order: Order | undefined; t: TFunction; tagProps?: TagProps}) => {
  switch (order?.status) {
    case OrderStatus.DRAFT: {
      return (
        <Tag minimal round {...tagProps}>
          {t('orders.statuses.draft')}
        </Tag>
      );
    }

    case OrderStatus.REVIEW: {
      return (
        <Tag minimal round intent='primary' {...tagProps}>
          {t('orders.statuses.review')}
        </Tag>
      );
    }

    case OrderStatus.INPROGRESS: {
      return (
        <Tag minimal round intent='warning' {...tagProps}>
          {t('orders.statuses.inprogress')}
        </Tag>
      );
    }

    case OrderStatus.READY: {
      return (
        <Tag minimal round intent='success' {...tagProps}>
          {t('orders.statuses.ready')}
        </Tag>
      );
    }

    case OrderStatus.FINISHED: {
      return (
        <Tag minimal round {...tagProps}>
          {t('orders.statuses.finished')}
        </Tag>
      );
    }

    default: {
      return null;
    }
  }
};

export default OrderStatusTag;
