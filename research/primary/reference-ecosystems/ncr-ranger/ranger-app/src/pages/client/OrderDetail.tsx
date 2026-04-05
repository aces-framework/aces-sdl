import {
  Breadcrumbs,
  Callout,
  H2,
  Menu,
  MenuItem,
  Popover,
  Tag,
} from '@blueprintjs/core';
import type React from 'react';
import {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import PageHolder from 'src/components/PageHolder';
import {getBreadcrumIntent} from 'src/utils';
import StepFooter from 'src/components/Order/client/StepFooter';
import TrainingObjectives from 'src/components/Order/client/TrainingObjectives';
import Structure from 'src/components/Order/client/Structure';
import Environment from 'src/components/Order/client/Environment';
import {type UpdateOrder, type Order, OrderStatus} from 'src/models/order';
import CustomElements from 'src/components/Order/client/CustomElements';
import Plot from 'src/components/Order/client/Plot';
import {UserRole} from 'src/models/userRoles';
import {type FormType} from 'src/models/routes';
import {
  useAdminUpdateOrderMutation,
  useClientUpdateOrderMutation,
} from 'src/slices/apiSlice';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import OrderStatusTag from 'src/components/Order/client/OrderStatusTag';

type OrderDetailProps = {
  order: Order | undefined;
  userRole: UserRole | 'loading' | undefined;
  stage: FormType | undefined;
};

function readyForNext(formType: string, order: Order | undefined): boolean {
  return (formType === 'training-objectives' && (order?.trainingObjectives?.length ?? 0) > 0)
  || (formType === 'structure' && (order?.structures?.length ?? 0) > 0)
  || (formType === 'environment' && (order?.environments?.length ?? 0) > 0)
  || formType === 'custom-elements'
  || (formType === 'plot' && (order?.plots?.length ?? 0) > 0);
}

const OrderDetail: React.FC<OrderDetailProps> = ({order, userRole, stage}) => {
  const {t} = useTranslation();
  const formType = stage ?? 'training-objectives';
  const [isOrderEditable, setIsOrderEditable] = useState(false);
  const [clientUpdateOrder, clientUpdatedOrder]
  = useClientUpdateOrderMutation();
  const [adminUpdateOrder, adminUpdatedOrder]
  = useAdminUpdateOrderMutation();

  const handleStatusChange = async (newStatus: OrderStatus) => {
    if (order?.id && order.status !== newStatus) {
      const orderUpdate: UpdateOrder = {
        status: newStatus,
      };

      await adminUpdateOrder({
        orderId: order.id,
        orderUpdate,
      });
    }
  };

  useEffect(() => {
    setIsOrderEditable(userRole === UserRole.CLIENT && order?.status === OrderStatus.DRAFT);
  }
  , [userRole, order]);

  useEffect(() => {
    if (clientUpdatedOrder.isSuccess) {
      toastSuccess('Order submitted successfully');
    } else if (clientUpdatedOrder.isError) {
      toastWarning('Failed to submit order');
    }

    if (adminUpdatedOrder.isSuccess) {
      toastSuccess('Order updated successfully');
    } else if (adminUpdatedOrder.isError) {
      toastWarning('Failed to update order');
    }
  }
  , [clientUpdatedOrder, adminUpdatedOrder]);

  return (
    <PageHolder>
      <div className='flex justify-start gap-6'>
        <H2>{t('orders.order')}: {order?.name}</H2>
        {userRole === UserRole.CLIENT && <OrderStatusTag order={order} t={t}/>}
        {userRole === UserRole.MANAGER && (
          <Popover
            placement='bottom'
            className='self-center'
            content={
              <Menu>
                <MenuItem
                  text={t('orders.statuses.draft')}
                  onClick={async () => {
                    await handleStatusChange(OrderStatus.DRAFT);
                  }}
                />
                <MenuItem
                  text={t('orders.statuses.review')}
                  onClick={async () => {
                    await handleStatusChange(OrderStatus.REVIEW);
                  }}
                />
                <MenuItem
                  text={t('orders.statuses.inprogress')}
                  onClick={async () => {
                    await handleStatusChange(OrderStatus.INPROGRESS);
                  }}
                />
                <MenuItem
                  text={t('orders.statuses.ready')}
                  onClick={async () => {
                    await handleStatusChange(OrderStatus.READY);
                  }}
                />
                <MenuItem
                  text={t('orders.statuses.finished')}
                  onClick={async () => {
                    await handleStatusChange(OrderStatus.FINISHED);
                  }}
                />
              </Menu>
            }
          >
            <OrderStatusTag
              tagProps={{large: true, rightIcon: 'caret-down', interactive: true}}
              order={order}
              t={t}/>
          </Popover>
        )}
      </div>
      <div className='my-4'>
        {order?.id && (
          <StepFooter
            readyForNext={readyForNext(formType, order)}
            orderId={order?.id}
            isUserClient={isOrderEditable}
            stage={formType}
            onSubmit={async () => {
              const orderUpdate: UpdateOrder = {
                status: OrderStatus.REVIEW,
              };

              await clientUpdateOrder({
                orderId: order.id,
                orderUpdate,
              });
            }}/>
        )}
      </div>
      <Breadcrumbs
        className='mt-4'
        breadcrumbRenderer={({icon, intent, text}) => (
          <Tag
            large
            round
            minimal
            icon={icon}
            intent={intent}

          >{text}
          </Tag>
        )}
        items={[
          {
            href: 'training-objectives',
            icon: 'new-object',
            text: t('orders.trainingObjectives'),
            intent: getBreadcrumIntent('training-objectives', formType),
          },
          {
            href: 'structure',
            icon: 'many-to-many',
            text: t('orders.structure'),
            intent: getBreadcrumIntent('structure', formType),
          },
          {
            href: 'environment',
            icon: 'globe-network',
            text: t('orders.environment'),
            intent: getBreadcrumIntent('environment', formType),
          },
          {
            href: 'custom-elements',
            icon: 'detection',
            text: t('orders.customElements'),
            intent: getBreadcrumIntent('custom-elements', formType),
          },
          {
            href: 'plot',
            icon: 'manual',
            text: t('orders.plot'),
            intent: getBreadcrumIntent('plot', formType),
          },
        ]}/>
      <div className='mt-4 min-h-full'>
        {order && formType === 'training-objectives'
        && (<TrainingObjectives order={order} isEditable={isOrderEditable}/>)}
        {order && formType === 'structure'
         && (<Structure order={order} isEditable={isOrderEditable}/>)}
        {order && formType === 'environment'
        && (<Environment order={order} isEditable={isOrderEditable}/>)}
        {order && formType === 'custom-elements'
         && (<CustomElements order={order} isEditable={isOrderEditable}/>)}
        {order && formType === 'plot' && (<Plot order={order} isEditable={isOrderEditable}/>)}
        {order && formType === 'final' && (
          <Callout intent='success' icon='info-sign'>
            {t('orders.submitExplenation')}
          </Callout>
        )}
      </div>
    </PageHolder>
  );
};

export default OrderDetail;
