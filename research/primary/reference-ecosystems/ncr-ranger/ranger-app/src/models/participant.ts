type NewParticipant = {
  userId: string;
  selector: string;
};

type Participant = {
  id: string;
  deploymentId: string;
  userId: string;
  selector: string;
};

export type {NewParticipant, Participant};
