import {BASE_URL} from 'src/constants';
import {getWebsocketBase} from 'src/utils';
import {type RootState} from 'src/store';
import {useSelector} from 'react-redux';
import {type Log, type LogLevel} from 'src/models/log';
import {useEffect, useRef, useState} from 'react';
import humanInterval from 'human-interval';

export const parseLog = (logString: string): Log | undefined => {
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) \[([^\]]+)] (.+)$/.exec(logString);
  if (match) {
    const datetime = match[1];
    const level = match[2] as LogLevel;
    const message = match[3];
    return {datetime, level, message};
  }

  return undefined;
};

const useLogStreaming = (logLevel?: LogLevel) => {
  const [logs, setLogs] = useState<Log[]>([]);
  const websocket = useRef<WebSocket | undefined>();
  const [trigger, setTrigger] = useState<boolean>(true);
  const token = useSelector((state: RootState) => state.user.token);

  useEffect(() => {
    if (!logLevel || !token) {
      return;
    }

    websocket.current = new WebSocket(
      `${getWebsocketBase()}${BASE_URL}/admin/log/websocket/${logLevel.toLowerCase()}`,
      `${token}`,
    );
    const thisInstance = websocket.current;
    thisInstance.addEventListener('message', (event: MessageEvent) => {
      if (typeof event.data === 'string') {
        const logString: string = event.data;
        const parsedLog = parseLog(logString);
        if (parsedLog) {
          setLogs(previousLogs => [...previousLogs, parsedLog]);
        }
      }
    });

    let timeout: number | undefined;

    thisInstance.addEventListener('close', () => {
      timeout = setTimeout(() => {
        if (websocket.current?.readyState !== WebSocket.OPEN) {
          setTrigger(current => !current);
        }
      }, humanInterval('3 seconds'));
    });

    return () => {
      if (timeout) {
        clearTimeout(timeout);
      }

      thisInstance.close();
    };
  }, [logLevel, token, trigger, setTrigger]);

  return logs;
};

export default useLogStreaming;
