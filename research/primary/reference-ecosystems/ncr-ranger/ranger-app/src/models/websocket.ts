import type {Deployment, DeploymentElement} from './deployment';
import type {DeploymentEvent, UpdateExercise} from './exercise';
import {type Score} from './score';

export enum WebsocketAdminMessageType {
  ExerciseUpdate = 'ExerciseUpdate',
  Deployment = 'Deployment',
  DeploymentElement = 'DeploymentElement',
  DeploymentElementUpdate = 'DeploymentElementUpdate',
  Score = 'Score',
  Event = 'Event',
}

export type WebsocketAdminWrapper = {exerciseId: string; ownId: string} & ({
  type: WebsocketAdminMessageType.Deployment;
  content: Deployment;
} | {
  type: WebsocketAdminMessageType.ExerciseUpdate;
  content: UpdateExercise;
} | {
  type: WebsocketAdminMessageType.DeploymentElement;
  content: DeploymentElement;
} | {
  type: WebsocketAdminMessageType.DeploymentElementUpdate;
  content: DeploymentElement;
} | {
  type: WebsocketAdminMessageType.Score;
  content: Score;
} | {
  type: WebsocketAdminMessageType.Event;
  content: DeploymentEvent;
}
);

export enum WebsocketParticipantMessageType {
  Score = 'Score',
}

export type WebsocketParticipantWrapper = {
  exerciseId: string;
  ownId: string;
} & ({
  type: WebsocketParticipantMessageType.Score;
  content: Score;
});
