export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
}

export type Log = {
  datetime: string;
  level: LogLevel;
  message: string;
};
