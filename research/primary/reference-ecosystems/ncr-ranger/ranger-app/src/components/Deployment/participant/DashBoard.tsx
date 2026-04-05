import React from 'react';
import {Divider, H2, H4, Icon} from '@blueprintjs/core';
import {type Banner} from 'src/models/exercise';
import {useKeycloak} from '@react-keycloak/web';
import {parseBannerForParticipant} from 'src/utils/banner';
import {
  useParticipantGetDeploymentQuery,
  useParticipantGetExerciseQuery,
} from 'src/slices/apiSlice';
import {useTranslation} from 'react-i18next';
import {formatStringToDateTime} from 'src/utils';
import DOMPurify from 'dompurify';
import ContentIFrame from 'src/components/ContentIFrame';

const ParticipantDashBoard = ({exerciseId, deploymentId, existingBanner}:
{exerciseId: string; deploymentId: string; existingBanner: Banner | undefined},
) => {
  const {t} = useTranslation();
  const {keycloak} = useKeycloak();
  const {data: exercise} = useParticipantGetExerciseQuery(exerciseId);
  const {data: deployment} = useParticipantGetDeploymentQuery(
    {exerciseId, deploymentId},
  );

  if (!deployment) {
    return (
      <div className='flex flex-col h-full min-h-screen'>
        <H2>{existingBanner?.name}</H2>
        <p>{existingBanner?.content}</p>
      </div>
    );
  }

  if (!exercise || !existingBanner || !keycloak.tokenParsed) {
    return (
      <div className='h-full min-h-screen'>
        <div className='pt-2 pb-4 flex justify-center'>
          <div className='flex-col pr-2'>
            <div className='flex'>
              <Icon icon='time' size={22}/>
              <H4 className='font-bold pl-2'>{t('deployments.startTime')}</H4>
            </div>
            <div>
              <p>{formatStringToDateTime(deployment.start)}</p>
            </div>
          </div>
          <Divider/>
          <div className='flex-col pl-2'>
            <div className='flex'>
              <Icon
                icon='time'
                size={22}
                style={{transform: 'rotate(90deg) translateX(-0.3rem) translateY(0.3rem)'}}
              />
              <H4 className='font-bold pl-2'>{t('deployments.endTime')}</H4>
            </div>
            <div>
              <p>{formatStringToDateTime(deployment.end)}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const encoded = new Uint8Array(existingBanner.content);
  let htmlString = new TextDecoder().decode(encoded);
  htmlString = DOMPurify.sanitize(htmlString);

  const parsedContent = parseBannerForParticipant(
    htmlString,
    exercise.name,
    deployment.name,
    keycloak.tokenParsed.preferred_username as string,
  );

  const parsedUint8Array = new TextEncoder().encode(parsedContent.content);
  return (
    <div className='h-full min-h-screen'>
      <div className='pt-2 pb-4 flex justify-center'>
        <div className='flex-col pr-2'>
          <div className='flex'>
            <Icon icon='time' size={22}/>
            <H4 className='font-bold pl-2'>{t('deployments.startTime')}</H4>
          </div>
          <div>
            <p>{formatStringToDateTime(deployment.start)}</p>
          </div>
        </div>
        <Divider/>
        <div className='flex-col pl-2'>
          <div className='flex'>
            <Icon
              icon='time'
              size={22}
              style={{transform: 'rotate(90deg) translateX(-0.3rem) translateY(0.3rem)'}}
            />
            <H4 className='font-bold pl-2'>{t('deployments.endTime')}</H4>
          </div>
          <div>
            <p>{formatStringToDateTime(deployment.end)}</p>
          </div>
        </div>
      </div>
      <ContentIFrame content={parsedUint8Array}/>
    </div>
  );
};

export default ParticipantDashBoard;
