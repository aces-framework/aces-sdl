import humanInterval from 'human-interval';
import {useEffect, useRef, useState} from 'react';
import {BASE_URL} from 'src/constants';
import type {WebsocketParticipantWrapper} from 'src/models/websocket';
import {WebsocketParticipantMessageType} from 'src/models/websocket';
import {apiSlice} from 'src/slices/apiSlice';
import type {AppDispatch, RootState} from 'src/store';
import {useAppDispatch} from 'src/store';
import {getWebsocketBase} from 'src/utils';
import {useSelector} from 'react-redux';

const websocketHandler = (
  dispatch: AppDispatch,
  entitySelector: string,
) => (event: MessageEvent<string>) => {
  const data: WebsocketParticipantWrapper = JSON.parse(event.data) as WebsocketParticipantWrapper;
  switch (data.type) {
    case WebsocketParticipantMessageType.Score: {
      const score = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('participantGetDeploymentScores', {
            exerciseId: score.exerciseId,
            deploymentId: score.deploymentId,
            entitySelector,
          },
          scores => {
            scores?.push(score);
          }));
      break;
    }

    default: {
      break;
    }
  }
};

const useParticipantExerciseStreaming = (
  exerciseId?: string,
  deploymentId?: string,
  entitySelector?: string,
) => {
  const dispatch = useAppDispatch();
  const websocket = useRef<WebSocket | undefined>();
  const [trigger, setTrigger] = useState<boolean>(true);
  const token = useSelector((state: RootState) => state.user.token);

  useEffect(() => {
    if (!token || !exerciseId || !deploymentId || !entitySelector) {
      return;
    }

    if (websocket.current === undefined
      || websocket.current.readyState !== WebSocket.OPEN
    ) {
      websocket.current = new WebSocket(
        // eslint-disable-next-line max-len
        `${getWebsocketBase()}${BASE_URL}/participant/exercise/${exerciseId}/deployment/${deploymentId}/entity/${entitySelector}/websocket`,
        `${token}`,
      );
      const thisInstance = websocket.current;
      thisInstance.addEventListener('message', websocketHandler(dispatch, entitySelector));
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
    }
  }, [dispatch, exerciseId, deploymentId, entitySelector, trigger, token, setTrigger]);
};

export default useParticipantExerciseStreaming;
