import { Session } from 'next-auth';
import { signOut, useSession } from 'next-auth/react';
import { ReactNode, useEffect } from 'react';

interface ClientSession extends Session {
  error?: string;
}

interface SessionCheckProps {
  children: ReactNode;
}

const SessionCheck = ({ children }: SessionCheckProps) => {
  const { data: session } = useSession();

  useEffect(() => {
    const clientSession = session as ClientSession;

    if (clientSession?.error === 'RefreshAccessTokenError') {
      signOut({
        callbackUrl: `/api/auth/signin?callbackUrl=${encodeURIComponent('/')}`,
      });
    }
  }, [session]);

  return <div>{children}</div>;
};

export default SessionCheck;
