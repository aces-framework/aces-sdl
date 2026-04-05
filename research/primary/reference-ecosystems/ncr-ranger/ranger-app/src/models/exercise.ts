
type ParticipantExercise = {
  id: string;
  name: string;
  updatedAt: string;
};

type NewExercise = {
  name: string;
  deploymentGroup: string;
  sdlSchema?: string;
  groupName?: string;
};

type Exercise = {
  id: string;
  createdAt: string;
  updatedAt: string;
} & NewExercise;

type UpdateExercise = NewExercise;

type Banner = {
  name: string;
  content: Uint8Array;
};

type BannerVariable = {
  name: string;
  content: Uint8Array;
};

type DeploymentEvent = {
  id: string;
  name: string;
  deploymentId: string;
  start: string;
  end: string;
  description?: string;
  hasTriggered: boolean;
  triggeredAt: string;
  eventInfoDataChecksum?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt: string;
};

type EventInfo = {
  checksum: string;
  name: string;
  fileName: string;
  fileSize: number;
  content: Uint8Array;
  createdAt: string;
};

export enum ActiveTab {
  Dash,
  Banner,
  Scores,
  Emails,
  EmailLogs,
  SDL,
  Accounts,
  EntitySelector,
  UserSubmissions,
  Events,
}

export type {
  Banner,
  BannerVariable,
  ParticipantExercise,
  NewExercise,
  Exercise,
  UpdateExercise,
  DeploymentEvent,
  EventInfo,
};
