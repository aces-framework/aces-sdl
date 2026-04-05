import React, {useEffect} from 'react';
import {Button, Callout, Intent, Tag} from '@blueprintjs/core';
import {useTranslation} from 'react-i18next';
import {type Exercise} from 'src/models/exercise';
import {EmailStatusType} from 'src/models/email';
import {toastWarning} from 'src/components/Toaster';
import {useAdminGetEmailsQuery} from 'src/slices/apiSlice';
import {openNewBlobWindow} from 'src/utils/email';
import {formatStringToDateTime} from 'src/utils';

const emailIntent = (status: EmailStatusType): Intent => {
  switch (status) {
    case EmailStatusType.Sent: {
      return Intent.SUCCESS;
    }

    case EmailStatusType.Failed: {
      return Intent.WARNING;
    }

    default: {
      return Intent.PRIMARY;
    }
  }
};

const EmailTable = ({exercise}: {readonly exercise: Exercise}) => {
  const {data: emails, error, isLoading, refetch} = useAdminGetEmailsQuery(exercise.id);
  const {t} = useTranslation();

  const viewEmailBodyInNewTab = (emailBodyHtml: string) => {
    openNewBlobWindow(emailBodyHtml);
  };

  useEffect(() => {
    async function fetchEmails() {
      await refetch();
    }

    fetchEmails().catch(() => {
      toastWarning(t('emails.errorFetchingEmails'));
    });
  }, [refetch, t]);

  if (isLoading) {
    return <Callout title={t('emails.fetchingEmails') ?? ''}/>;
  }

  if (error) {
    return <Callout title={t('emails.fetchingEmailsFail') ?? ''}/>;
  }

  if (emails && emails.length > 0) {
    const sortedEmails = [...emails].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );

    return (
      <div>
        <table className='bp5-html-table bp5-html-table-striped bp5-html-table-bordered'>
          <thead>
            <tr>
              <th>{t('emails.status')}</th>
              <th>{t('emails.timestamp')}</th>
              <th>{t('emails.from')}</th>
              <th>{t('emails.to')}</th>
              <th>{t('emails.replyTo')}</th>
              <th>{t('emails.cc')}</th>
              <th>{t('emails.bcc')}</th>
              <th>{t('emails.subject')}</th>
              <th>{t('emails.body')}</th>
            </tr>
          </thead>
          <tbody>
            {sortedEmails.map(email => (
              <tr key={email.id}>
                <td>
                  <Tag intent={emailIntent(email.statusType)}>
                    {email.statusType}
                  </Tag>
                </td>
                <td>{formatStringToDateTime(email.createdAt)}</td>
                <td>{email.fromAddress}</td>
                <td>{email.toAddresses}</td>
                <td>{email.replyToAddresses}</td>
                <td>{email.ccAddresses}</td>
                <td>{email.bccAddresses}</td>
                <td>{email.subject}</td>
                <td>
                  <Button
                    small
                    intent={Intent.PRIMARY}
                    onClick={() => {
                      viewEmailBodyInNewTab(email.body);
                    }}
                  >
                    {t('emails.viewBody')}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>

        </table>
      </div>
    );
  }

  return (
    <Callout title={t('emails.noEmails') ?? ''}/>
  );
};

export default EmailTable;
