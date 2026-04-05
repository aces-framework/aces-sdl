import type React from 'react';
import {LogLevel} from 'src/models/log';
import type {Log} from 'src/models/log';
import {useLogs} from 'src/contexts/LogContext';
import {useEffect, useState, useRef} from 'react';
import {useTranslation} from 'react-i18next';
import {Callout, H2} from '@blueprintjs/core';
import {formatStringToDateTime} from 'src/utils';

const logSeverity = {
  DEBUG: 1,
  INFO: 2,
  WARN: 3,
  ERROR: 4,
};

const logSeverityColors = {
  DEBUG: 'bg-yellow-100',
  INFO: 'bg-green-100',
  WARN: 'bg-orange-100',
  ERROR: 'bg-red-100',
};

const LogView: React.FC = () => {
  const tableRef = useRef<HTMLDivElement>(null);
  const {t} = useTranslation();

  const {logs, selectedLogLevel, setSelectedLogLevel} = useLogs();

  const logLevels = Object.values(LogLevel);

  const [filteredLogs, setFilteredLogs] = useState<Log[]>([]);

  useEffect(() => {
    setFilteredLogs([]);

    const timeoutId = setTimeout(() => {
      const selectedSeverity = logSeverity[selectedLogLevel];
      const newFilteredLogs = logs.filter(log => logSeverity[log.level] >= selectedSeverity);
      setFilteredLogs(newFilteredLogs);
    }, 50);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [selectedLogLevel, logs]);

  useEffect(() => {
    if (tableRef.current) {
      tableRef.current.scrollTop = tableRef.current.scrollHeight;
    }
  }, [filteredLogs]);

  return (
    <>
      <H2>{t('menu.logs')}</H2>
      <div className='container mx-auto'>
        <div className='relative inline-block w-full text-gray-700'>
          <select
            value={selectedLogLevel}
            // eslint-disable-next-line max-len
            className='w-full h-10 pl-3 pr-6 text-base placeholder-gray-600 border rounded-lg appearance-none'
            onChange={event => {
              const eventValue = event.target.value;
              const newLevel = eventValue as LogLevel;
              setSelectedLogLevel(newLevel);
            }}
          >
            {logLevels.map(level => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
          <div className='absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none'>
            <svg
              className='w-4 h-4 text-gray-400'
              viewBox='0 0 24 24'
              fill='none'
              xmlns='http://www.w3.org/2000/svg'
            >
              <path d='M7 10l5 5 5-5H7z' fill='currentColor'/>
            </svg>
          </div>
        </div>

        <div ref={tableRef} className='overflow-y-auto mt-4 max-h-[50vh]'>
          {filteredLogs.length === 0 ? (
            <Callout title={t('log.empty') ?? ''}/>
          ) : (
            <table className='min-w-full divide-y divide-gray-200'>
              <thead className='bg-gray-50 sticky top-0'>
                <tr>
                  <th
                    // eslint-disable-next-line max-len
                    className='px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4'
                  >{t('log.date')}
                  </th>
                  <th
                    // eslint-disable-next-line max-len
                    className='px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4'
                  >{t('log.level')}
                  </th>
                  <th
                    // eslint-disable-next-line max-len
                    className='px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-2/4'
                  >{t('log.message')}
                  </th>
                </tr>
              </thead>
              <tbody className='bg-white divide-y divide-gray-200'>
                {filteredLogs.map(log => (
                  <tr key={log.datetime} className={logSeverityColors[log.level]}>
                    <td className='px-6 py-4 whitespace-nowrap'>
                      {formatStringToDateTime(log.datetime)}
                    </td>
                    <td className='px-6 py-4 whitespace-nowrap'>{log.level}</td>
                    <td className='px-6 py-4'>{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
};

export default LogView;
