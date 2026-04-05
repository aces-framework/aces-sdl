import type React from 'react';
import {createContext, useState, useContext, useMemo} from 'react';
import {type Log, LogLevel} from 'src/models/log';
import useLogStreaming from 'src/hooks/useLogStreaming';

export type LogContextProps = {
  selectedLogLevel: LogLevel;
  setSelectedLogLevel: React.Dispatch<React.SetStateAction<LogLevel>>;
  logs: Log[];
};

const LogContext = createContext<LogContextProps | undefined>(undefined);

type LogProviderProps = {
  children: React.ReactNode;
};

export const LogProvider: React.FC<LogProviderProps> = ({children}) => {
  const [selectedLogLevel, setSelectedLogLevel] = useState<LogLevel>(LogLevel.INFO);
  const logs = useLogStreaming(LogLevel.DEBUG);

  const value = useMemo(() => ({
    selectedLogLevel,
    setSelectedLogLevel,
    logs,
  }), [selectedLogLevel, logs]);

  return (
    <LogContext.Provider value={value}>
      {children}
    </LogContext.Provider>
  );
};

export const useLogs = () => {
  const context = useContext(LogContext);
  if (!context) {
    throw new Error('useLogs must be used within a LogProvider');
  }

  return context;
};
