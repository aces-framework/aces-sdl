import {
  Button,
  Callout,
  Card,
  Elevation,
  H3,
  Tag,
} from '@blueprintjs/core';
import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastSuccess, toastWarning} from 'src/components/Toaster';
import {
  type Order,
  type CustomElement,
  type NewCustomElement,
} from 'src/models/order';
import {
  useClientAddCustomElementMutation,
  useClientDeleteCustomElementMutation,
  useClientUpdateCustomElementMutation,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import {useSelector} from 'react-redux';
import {tokenSelector} from 'src/slices/userSlice';
import {BASE_URL} from 'src/constants';
import {dowloadFile} from 'src/utils';
import CustomElementDialog from './CustomElementDialog';

const orderBase = `${BASE_URL}/client/order`;

const CustomElements = ({order, isEditable}: {order: Order; isEditable: boolean}) => {
  const {t} = useTranslation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [addCustomElement, {error, data: addData}] = useClientAddCustomElementMutation();
  const [deleteCustomElement, {error: deleteError}] = useClientDeleteCustomElementMutation();
  const [updateCustomElement, {error: updateError, data: updateData}]
        = useClientUpdateCustomElementMutation();
  const [editedCustomElement, setEditedCustomElement]
        = useState<CustomElement | undefined>();
  const {customElements: potentialCustomElements} = order;
  const sortedCustomElements = [...(potentialCustomElements ?? [])]
    .sort(sortByProperty('name', 'desc'));
  const token = useSelector(tokenSelector);
  const [customElementFile, setCustomElementFile] = useState<File | undefined>();

  useEffect(() => {
    if (addData && customElementFile) {
      const formData = new FormData();
      formData.append('file', customElementFile);
      fetch(`${orderBase}/${order.id}/custom_element/${addData.id}/file`, {
        method: 'POST',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: formData,
      }).then(response => {
        if (response.ok) {
          toastSuccess(t('orders.customElement.fileUploaded'));
        } else {
          toastWarning(t('orders.customElement.failedToUploadFile'));
        }

        setCustomElementFile(undefined);
      })
        .catch(() => {
          toastWarning(t('orders.customElement.failedToUploadFile'));
        });
    }
  }
  , [addData, customElementFile, order.id, token, t]);

  useEffect(() => {
    if (updateData && customElementFile) {
      const formData = new FormData();
      formData.append('file', customElementFile);
      fetch(`${orderBase}/${order.id}/custom_element/${updateData.id}/file`, {
        method: 'POST',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: formData,
      }).then(response => {
        if (response.ok) {
          toastSuccess(t('orders.customElement.fileUploaded'));
        } else {
          toastWarning(t('orders.customElement.failedToUploadFile'));
        }

        setCustomElementFile(undefined);
      })
        .catch(() => {
          toastWarning(t('orders.customElement.failedToUploadFile'));
        });
    }
  }
  , [updateData, customElementFile, order.id, token, t]);

  useEffect(() => {
    if (error) {
      toastWarning(t(
        'orders.customElement.failedToAdd',
      ));
    }
  }, [error, t]);

  useEffect(() => {
    if (deleteError) {
      toastWarning(t(
        'orders.customElement.failedToDelete',
      ));
    }
  }, [deleteError, t]);

  useEffect(() => {
    if (updateError) {
      toastWarning(t(
        'orders.customElement.failedToUpdate',
      ));
    }
  }, [updateError, t]);

  const onHandleSubmit = async (formContent: NewCustomElement, file?: File) => {
    setIsDialogOpen(false);
    setCustomElementFile(file);
    if (editedCustomElement) {
      await updateCustomElement({
        customElement: {
          ...editedCustomElement,
          ...formContent,
        },
        orderId: order.id,
        customElementId: editedCustomElement.id,
      });
    } else {
      await addCustomElement({
        newCustomElement: formContent,
        orderId: order.id,
      });
    }

    setEditedCustomElement(undefined);
  };

  const enviroments = order.environments ?? [];

  return (
    <>
      <CustomElementDialog
        crossClicked={() => {
          setIsDialogOpen(false);
        }}
        isOpen={isDialogOpen}
        editableCustomElement={editedCustomElement}
        order={order}
        onSubmit={onHandleSubmit}
      />
      <Callout intent='primary' icon='info-sign'>
        {t('orders.customElement.explenation')}
      </Callout>
      <div className='mt-4 flex gap-4 justify-between items-start'>
        <div className='flex flex-col gap-4 grow'>
          {sortedCustomElements.map(customElement => (
            <Card key={customElement.id} className='min-w-0' elevation={Elevation.TWO}>
              <div className='flex gap-2'>
                <H3
                  className='truncate max-w-xl m-0'
                >
                  {customElement.name}
                </H3>
                {enviroments
                  .find(environment => environment.id === customElement.environmentId)?.name ? (
                    <Tag
                      minimal
                      round
                      intent='success'
                      icon='inheritance'
                    >
                      {enviroments
                        .find(environment => environment.id === customElement.environmentId)?.name}
                    </Tag>
                  ) : null}
              </div>
              <div className='flex flex-wrap gap-4 mt-2'>
                <p>{customElement.description}</p>
              </div>
              <div className='flex mt-4 gap-2 justify-end'>
                <Button
                  icon='download'
                  intent='primary'
                  onClick={async () => {
                    const fileLink = `
                      ${orderBase}/${order.id}/custom_element/${customElement.id}/file`;
                    await dowloadFile(
                      fileLink,
                      token ?? '',
                      `${customElement.name}.zip`,
                      () => {
                        toastWarning(t('orders.customElement.failedToDownloadFile'));
                      });
                  }}
                >
                  {t('orders.customElement.content')}
                </Button>
                <Button
                  disabled={!isEditable}
                  intent='danger'
                  onClick={async () => {
                    await fetch(
                      `${orderBase}/${order.id}/custom_element/${customElement.id}/file`, {
                        method: 'DELETE',
                        headers: {
                          Authorization: token ? `Bearer ${token}` : '',
                        },
                      });
                    await deleteCustomElement({
                      orderId: order.id,
                      customElementId: customElement.id,
                    });
                  }}
                >
                  {t('common.delete')}
                </Button>
                <Button
                  disabled={!isEditable}
                  intent='warning'
                  onClick={() => {
                    setEditedCustomElement(customElement);
                    setIsDialogOpen(true);
                  }}
                >
                  {t('common.edit')}
                </Button>
              </div>
            </Card>
          ))}
        </div>
        <Button
          large
          disabled={!isEditable}
          className='shrink-0'
          intent='primary'
          onClick={() => {
            setEditedCustomElement(undefined);
            setIsDialogOpen(true);
          }}
        >
          {t('orders.customElement.add')}
        </Button>
      </div>
    </>
  );
};

export default CustomElements;
