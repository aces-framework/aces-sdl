import nunjucks from 'nunjucks';

export const parseBannerForParticipant = (
  bannerContent: string,
  exerciseName: string,
  deploymentName: string,
  username: string,
) => ({
  content: nunjucks.renderString(bannerContent, {
    exerciseName,
    deploymentName,
    username,
  }),
});
