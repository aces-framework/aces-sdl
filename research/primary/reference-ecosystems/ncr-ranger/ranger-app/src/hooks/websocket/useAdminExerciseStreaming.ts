import humanInterval from 'human-interval';
import {useEffect, useRef, useState} from 'react';
import {BASE_URL} from 'src/constants';
import type {WebsocketAdminWrapper} from 'src/models/websocket';
import {WebsocketAdminMessageType} from 'src/models/websocket';
import {apiSlice} from 'src/slices/apiSlice';
import type {AppDispatch, RootState} from 'src/store';
import {useAppDispatch} from 'src/store';
import {getWebsocketBase} from 'src/utils';
import {useSelector} from 'react-redux';

const websocketHandler = (
  dispatch: AppDispatch,
) => (event: MessageEvent<string>) => {
  const data: WebsocketAdminWrapper = JSON.parse(event.data) as WebsocketAdminWrapper;
  switch (data.type) {
    case WebsocketAdminMessageType.ExerciseUpdate: {
      const exerciseUpdate = data.content;
      dispatch(
        apiSlice.util.updateQueryData('adminGetExercise',
          data.exerciseId,
          exercise => {
            Object.assign(exercise, exerciseUpdate);
          }));
      break;
    }

    case WebsocketAdminMessageType.Deployment: {
      const deployment = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('adminGetDeployments',
            deployment.exerciseId,
            deployments => {
              deployments?.push(deployment);
            }));
      break;
    }

    case WebsocketAdminMessageType.DeploymentElement: {
      const deploymentElement = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('adminGetDeploymentElements', {
            exerciseId: data.exerciseId,
            deploymentId: deploymentElement.deploymentId,
          }, deploymentElements => {
            deploymentElements?.push(deploymentElement);
          }));
      break;
    }

    case WebsocketAdminMessageType.DeploymentElementUpdate: {
      const deploymentElementUpdate = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('adminGetDeploymentElements', {
            exerciseId: data.exerciseId,
            deploymentId: deploymentElementUpdate.deploymentId,
          }, deploymentElements => {
            const element = deploymentElements?.find(
              deploymentElement =>
                deploymentElement.id === deploymentElementUpdate.id,
            );
            if (element) {
              Object.assign(element, deploymentElementUpdate);
            }
          }));
      break;
    }

    case WebsocketAdminMessageType.Score: {
      const score = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('adminGetDeploymentScores', {
            exerciseId: score.exerciseId,
            deploymentId: score.deploymentId,
          },
          scores => {
            scores?.push(score);
          }));
      break;
    }

    case WebsocketAdminMessageType.Event: {
      const eventUpdate = data.content;
      dispatch(
        apiSlice.util
          .updateQueryData('adminGetEvents', {
            exerciseId: data.exerciseId,
            deploymentId: eventUpdate.deploymentId,
          }, (deploymentEvents = []) => {
            const oldEventIndex = deploymentEvents.findIndex(
              deploymentEvent =>
                deploymentEvent.id === eventUpdate.id,
            );
            if (oldEventIndex === -1) {
              deploymentEvents.push(eventUpdate);
            } else {
              deploymentEvents[oldEventIndex]
              = {...deploymentEvents[oldEventIndex], ...eventUpdate};
            }

            return deploymentEvents;
          }));
      break;
    }

    default: {
      break;
    }
  }
};

const useAdminExerciseStreaming = (exerciseId?: string) => {
  const dispatch = useAppDispatch();
  const websocket = useRef<WebSocket | undefined>();
  const [trigger, setTrigger] = useState<boolean>(true);
  const token = useSelector((state: RootState) => state.user.token);

  useEffect(() => {
    if (!token || !exerciseId) {
      return;
    }

    if (websocket.current === undefined
        || websocket.current.readyState !== WebSocket.OPEN
    ) {
      websocket.current = new WebSocket(
        `${getWebsocketBase()}${BASE_URL}/admin/exercise/${exerciseId}/websocket`,
        `${token}`,
      );
      const thisInstance = websocket.current;
      thisInstance.addEventListener('message', websocketHandler(dispatch));
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
  }, [dispatch, exerciseId, trigger, token, setTrigger]);
};

export default useAdminExerciseStreaming;
