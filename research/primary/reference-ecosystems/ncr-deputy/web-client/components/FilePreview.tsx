import { useRouter } from 'next/router';
import type { Slide } from 'yet-another-react-lightbox';
import Lightbox from 'yet-another-react-lightbox';
import Thumbnails from 'yet-another-react-lightbox/plugins/thumbnails';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Inline from 'yet-another-react-lightbox/plugins/inline';
import Video from 'yet-another-react-lightbox/plugins/video';
import type { Project } from '../interfaces/Project';
import 'yet-another-react-lightbox/styles.css';
import 'yet-another-react-lightbox/plugins/thumbnails.css';
import CodePreview from './CodePreview';

const FilePreview = ({
  packageData,
  isYanked,
}: {
  packageData: Project;
  isYanked: boolean;
}) => {
  const { asPath } = useRouter();
  const nameAndVersion = asPath.split('/packages/')[1];
  const slides: Slide[] = [];
  const codeBlocks: JSX.Element[] = [];

  if (!packageData.content.preview || isYanked) {
    return null;
  }

  packageData.content.preview.forEach((preview) => {
    if (preview.type === 'picture') {
      preview.value.forEach((filepath) => {
        slides.push({
          height: 10000,
          width: 10000,
          src: `/api/v1/package/${nameAndVersion}/path/${filepath}`,
        });
      });
    }

    if (preview.type === 'video') {
      preview.value.forEach((filepath) => {
        slides.push({
          height: 10000,
          width: 10000,
          type: 'video',
          sources: [
            {
              src: `/api/v1/package/${nameAndVersion}/path/${filepath}`,
              type: 'video/mp4',
            },
          ],
        });
      });
    }

    if (preview.type === 'code') {
      preview.value.forEach((filepath) => {
        codeBlocks.push(<CodePreview key={filepath} filepath={filepath} />);
      });
    }
  });

  if (slides.length > 0) {
    return (
      <div>
        <Lightbox
          slides={slides}
          inline={{ style: { aspectRatio: '3 / 2' } }}
          video={{ preload: 'none' }}
          plugins={[Video, Thumbnails, Inline, Fullscreen]}
        />
        {codeBlocks.length > 0 && <div>{codeBlocks}</div>}
      </div>
    );
  }

  if (codeBlocks.length > 0) {
    return <div>{codeBlocks}</div>;
  }

  return null;
};

export default FilePreview;
