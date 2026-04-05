import {
  Button,
  Callout,
  H5,
  H6,
  Tag,
  Tree,
  type TreeNodeInfo,
} from '@blueprintjs/core';
import React, {useCallback, useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {toastWarning} from 'src/components/Toaster';
import {type Order, type NewStructure, type Structure} from 'src/models/order';
import {
  useClientAddStructureMutation,
  useClientDeleteStructureMutation,
  useClientUpdateStructureMutation,
} from 'src/slices/apiSlice';
import {sortByProperty} from 'sort-by-property';
import {type TFunction} from 'i18next';
import StructureDialog from './StructureDialog';

const numberOfParents = (structure: Structure, structures: Structure[]): number => {
  if (structure.parentId === null) {
    return 0;
  }

  const parent = structures.find(s => s.id === structure.parentId);
  if (!parent) {
    return 0;
  }

  return 1 + numberOfParents(parent, structures);
};

const createStructureTree = (
  order: Order,
  isUserClient: boolean,
  functions: {
    deleteFields: {
      text: string;
      callback: (structureId: string) => Promise<void>;
    };
    editFields: {
      text: string;
      callback: (structure: Structure) => Promise<void>;
    };
    t: TFunction;
  },
  openNodes: string[],
): TreeNodeInfo[] => {
  const {structures: exposedStructures} = order;
  const structures = exposedStructures ?? [];
  const {deleteFields, editFields, t} = functions;
  const {text: deleteText, callback: deleteStructureCallback} = deleteFields;
  const {text: editText, callback: editStructureCallback} = editFields;
  const initialStructure = [...structures].sort(sortByProperty('name', 'desc'));
  const sortedStructure: Structure[] = [];

  let backupCounter = 0;
  while (initialStructure.length > 0) {
    if (backupCounter > structures.length ** 2) {
      break;
    }

    const lastElement = initialStructure.pop();
    if (!lastElement) {
      break;
    }

    if (lastElement.parentId === null) {
      sortedStructure.push(lastElement);
    } else {
      const parentElement = sortedStructure
        .find(structure => structure.id === lastElement.parentId);
      if (parentElement) {
        sortedStructure.splice(sortedStructure.indexOf(parentElement) + 1, 0, lastElement);
      } else {
        initialStructure.unshift(lastElement);
      }
    }

    backupCounter += 1;
  }

  return sortedStructure.map(structure => {
    const isExpanded = openNodes.includes(structure.id);
    const rightShift = numberOfParents(structure, structures) * 1.1;

    return ({
      id: structure.id,
      className: 'my-3',
      hasCaret: true,
      isExpanded,
      label: (
        <div className='flex flex-col'>
          <div
            className='flex'
            style={{
              paddingLeft: `${rightShift}rem`,
            }}
          >
            <H5>
              {structure.name}:
            </H5>
            <span className='ml-2'>
              {structure.description}
            </span>
          </div>
          {isExpanded && (
            <div
              className='flex flex-col'
              style={{
                paddingLeft: `${rightShift}rem`,
              }}
            >
              <div className='flex mb-2 items-center'>
                <H6 className='m-0'>{t('orders.structureElements.weaknesses')}: </H6>
                {(structure.weaknesses ?? []).map(weakness => (
                  <Tag
                    key={weakness.id}
                    round
                    minimal
                    intent='warning'
                    className='ml-2'
                  >
                    {weakness.weakness}
                  </Tag>
                ))}
              </div>
              <div className='flex mb-2 items-center'>
                <H6 className='m-0'>{t('orders.structureElements.skills')}: </H6>
                {(structure.skills ?? []).map(skill => (
                  <Tag
                    key={skill.id}
                    round
                    minimal
                    intent='primary'
                    className='ml-2'
                  >
                    {skill.skill}
                  </Tag>
                ))}
              </div>
              <div className='flex mb-2 items-center'>
                <H6 className='m-0'>
                  {t('orders.structureElements.connectedTrainingObjectives')}:
                </H6>
                {(structure.trainingObjectiveIds ?? []).map(connection => (
                  <Tag
                    key={connection.id}
                    round
                    minimal
                    intent='success'
                    className='ml-2'
                  >
                    {order.trainingObjectives
                      ?.find(
                        objective => objective.id === connection.trainingObjectiveId,
                      )?.objective ?? ''}
                  </Tag>
                ))}
              </div>
            </div>
          )}
        </div>
      ),
      secondaryLabel: (
        <div className='flex gap-2'>
          <Button
            disabled={!isUserClient}
            className='pt-1'
            intent='warning'
            onClick={async () => {
              await editStructureCallback(structure);
            }}
          >
            {editText}
          </Button>
          <Button
            disabled={!isUserClient}
            className='pt-1'
            intent='danger'
            onClick={async () => {
              await deleteStructureCallback(structure.id);
            }}
          >
            {deleteText}
          </Button>
        </div>
      ),
      nodeData: {
        structure,
        numberOfParents: numberOfParents(structure, structures),
      },
    });
  });
};

const StructureElement = ({order, isEditable}: {order: Order; isEditable: boolean}) => {
  const {t} = useTranslation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [addStructure, {error}] = useClientAddStructureMutation();
  const [deleteStructure, {error: deleteError}] = useClientDeleteStructureMutation();
  const [updateStructure, {error: updateError}]
      = useClientUpdateStructureMutation();
  const [editedStructure, setEditedStructure]
      = useState<Structure | undefined>();
  const [openNodes, setOpenNodes] = useState<string[]>([]);

  useEffect(() => {
    if (error) {
      toastWarning(t(
        'orders.structureElements.failedtoAdd',
      ));
    }
  }, [error, t]);

  useEffect(() => {
    if (deleteError) {
      toastWarning(t(
        'orders.structureElements.failedToDelete',
      ));
    }
  }, [deleteError, t]);

  useEffect(() => {
    if (updateError) {
      toastWarning(t(
        'orders.structureElements.failedToUpdate',
      ));
    }
  }, [updateError, t]);

  const onHandleSubmit = async (formContent: NewStructure) => {
    setIsDialogOpen(false);
    if (editedStructure) {
      await updateStructure({
        newStructure: {
          ...editedStructure,
          ...formContent,
        },
        orderId: order.id,
        structureId: editedStructure.id,
      });
    } else {
      await addStructure({
        newStructure: formContent,
        orderId: order.id,
      });
    }

    setEditedStructure(undefined);
  };

  const handleDeleteStructure = useCallback(async (structureId: string) => {
    await deleteStructure({
      orderId: order.id,
      structureId,
    });
  }, [order.id, deleteStructure]);

  const handleEditStructure = useCallback(async (structure: Structure) => {
    setEditedStructure(structure);
    setIsDialogOpen(true);
  }, []);

  const tree: TreeNodeInfo[] = React.useMemo(() => {
    if (!order.structures) {
      return [];
    }

    return createStructureTree(
      order,
      isEditable,
      {
        deleteFields: {
          text: t('orders.structureElements.delete'),
          callback: handleDeleteStructure,
        },
        editFields: {
          text: t('orders.structureElements.edit'),
          callback: handleEditStructure,
        },
        t,
      },
      openNodes,
    );
  }, [order, isEditable, t, handleDeleteStructure, handleEditStructure, openNodes]);

  return (
    <>
      <StructureDialog
        order={order}
        crossClicked={() => {
          setIsDialogOpen(false);
        }}
        isOpen={isDialogOpen}
        editableStructure={editedStructure}
        onSubmit={onHandleSubmit}
      />
      <Callout intent='primary' icon='info-sign'>
        {t('orders.structureElements.explenation')}
      </Callout>
      <div className='mt-4 flex gap-4 justify-between items-start'>
        <div className='flex flex-col gap-4 grow structure-tree'>
          <Tree
            contents={tree}
            onNodeExpand={node => {
              setOpenNodes([...openNodes, node.id.toString()]);
            }}
            onNodeCollapse={node => {
              setOpenNodes(openNodes.filter(id => id !== node.id.toString()));
            }}
          />
        </div>
        <Button
          large
          disabled={!isEditable}
          className='shrink-0'
          intent='primary'
          onClick={() => {
            setEditedStructure(undefined);
            setIsDialogOpen(true);
          }}
        >
          {t('orders.structureElements.add')}
        </Button>
      </div>
    </>
  );
};

export default StructureElement;

