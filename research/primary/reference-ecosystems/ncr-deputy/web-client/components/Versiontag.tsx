import { Intent, Tag } from '@blueprintjs/core';

const VersionTag = ({
  version,
  intent = 'none',
}: {
  version: string;
  // eslint-disable-next-line react/require-default-props
  intent?: Intent;
}) => (
  <Tag large minimal round intent={intent}>
    v{version}
  </Tag>
);

export default VersionTag;
