import React from 'react';
import {useTranslation} from 'react-i18next';
import {
  type TrainingLearningObjective,
  ExerciseRoleOrder,
  type ScoringMetadata,
} from 'src/models/scenario';
import {
  flattenEntities,
  getUniqueRoles,
  groupTloMapsByRoles,
  tableHeaderBgColor,
  tableRowBgColor,
} from 'src/utils';
import {type Score} from 'src/models/score';
import TloTableRow from './TloTableRow';

const TloTable = ({scoringData, scores, tloMap}:
{scoringData: ScoringMetadata | undefined;
  scores: Score[] | undefined;
  tloMap: Record<string, TrainingLearningObjective> | undefined;
}) => {
  const {t} = useTranslation();

  if (tloMap && scoringData) {
    const flattenedEntities = flattenEntities(scoringData.entities);
    const roles = getUniqueRoles(flattenedEntities);
    roles.sort((a, b) => ExerciseRoleOrder[a] - ExerciseRoleOrder[b]);
    const tloMapsByRole = groupTloMapsByRoles(
      flattenedEntities, tloMap, roles);

    return (
      <div className='flex flex-col'>
        {roles.map(role => {
          const tloMap = tloMapsByRole[role];
          if (tloMap && Object.keys(tloMap).length > 0) {
            const tloKeys = Object.keys(tloMap);
            return (
              <div key={role} className='w-full text-center'>
                <table
                  className='w-full mt-6 border border-separate border-spacing-0
                  border-neutral-500 rounded-xl overflow-hidden'
                >
                  <thead
                    className={tableHeaderBgColor[role]}
                  >
                    <tr>
                      <th
                        className='px-6 py-2 border-r border-b border-neutral-500 text-lg'
                        rowSpan={2}
                      >
                        {t('tloTable.headers.tlo')}
                      </th>
                      <th
                        className='px-6 py-2 border-r border-b border-neutral-500 text-lg'
                        rowSpan={2}
                      >
                        {t('tloTable.headers.evaluation')}
                      </th>
                      <th
                        className='px-6 py-2 border-b border-neutral-500 text-lg'
                        colSpan={3}
                      >
                        {t('tloTable.headers.metrics')}
                      </th>
                    </tr>
                    <tr className='flex border-b border-neutral-500 text-sm'>
                      <th className='pl-1 w-2/5'>{t('tloTable.headers.name')}</th>
                      <th className='px-1 w-2/5'>{t('tloTable.headers.vm')}</th>
                      <th className='pr-1 w-1/5'>{t('tloTable.headers.points')}</th>
                    </tr>
                  </thead>
                  <tbody className={tableRowBgColor[role]}>
                    { tloKeys.map(tloKey => (
                      <TloTableRow
                        key={tloKey}
                        scoringData={scoringData}
                        scores={scores}
                        tloKey={tloKey}
                        tlo={tloMap[tloKey]}/>
                    )) }
                  </tbody>
                </table>
              </div>
            );
          }

          return null;
        },
        )}
      </div>
    );
  }

  return null;
};

export default TloTable;
