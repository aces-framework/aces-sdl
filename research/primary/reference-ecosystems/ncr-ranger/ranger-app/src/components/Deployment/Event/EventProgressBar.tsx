import React, {useState, useEffect} from 'react';
import {DateTime} from 'luxon';
import {type DeploymentEvent} from 'src/models/exercise';
import {useTranslation} from 'react-i18next';
import {ProgressBar} from '@blueprintjs/core';

const ProgressBarWithTimer = ({event, allNodesHaveTriggered}:
{event: DeploymentEvent; allNodesHaveTriggered: boolean}) => {
  const {t} = useTranslation();
  const [timeLeft, setTimeLeft] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      const now = DateTime.utc();
      const end = DateTime.fromISO(event.end, {zone: 'UTC'});
      const duration = end.diff(now);

      setTimeLeft(duration.toFormat('hh:mm:ss'));
    }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, [event]);

  const now = DateTime.utc();
  const end = DateTime.fromISO(event.end, {zone: 'UTC'});
  const start = DateTime.fromISO(event.start, {zone: 'UTC'});
  const totalDuration = end.diff(start, 'milliseconds').milliseconds;
  const elapsed = now.diff(start, 'milliseconds').milliseconds;
  const progress = Math.min(100, (elapsed / totalDuration) * 100);
  const futureStart = start.diff(now);

  if (allNodesHaveTriggered) {
    return (
      <div className='items-center w-full mb-2'>
        <div className='flex text-sm justify-center italic'>
          { t('deployments.events.eventHasTriggered')}
        </div>
        <ProgressBar
          intent='success'
          stripes={false}
          value={1}
        />
      </div>
    );
  }

  return (
    <div className='items-center w-full mb-2'>
      {now > start && now < end && (
        <div className='flex text-sm justify-center italic'>
          {t('deployments.events.eventWillCloseIn')} {timeLeft}
        </div>
      )}

      {now < start ? (
        <div className='flex text-sm justify-center italic'>
          {t('deployments.events.eventWillOpenIn')} {futureStart.toFormat('hh:mm:ss')}
        </div>
      ) : (now > end && (
        <div className='flex text-sm justify-center italic'>
          {t('deployments.events.eventWindowClosed')}
        </div>
      ))}
      <ProgressBar
        intent={now < end ? 'primary' : 'none'}
        stripes={false}
        value={progress / 100}
      />
    </div>
  );
};

export default ProgressBarWithTimer;
