import { useRouter } from 'next/router';
import type { Fetcher } from 'swr';
import useSWR from 'swr';
import { CodeBlock, dracula } from 'react-code-blocks';

const codeFetcher: Fetcher<string, string> = async (...url) =>
  fetch(...url).then(async (res) => res.text());

const CodePreview = ({ filepath }: { filepath: string }) => {
  const { asPath } = useRouter();
  const nameAndVersion = asPath.split('/packages/')[1];
  const { data: codeFileContent } = useSWR(
    `/api/v1/package/${nameAndVersion}/path/${filepath}`,
    codeFetcher
  );

  if (!codeFileContent) {
    return null;
  }

  return (
    <pre>
      <hr />
      <h4>{filepath}</h4>
      <CodeBlock
        text={codeFileContent}
        language={filepath.split('.').slice(-1)[0].toLowerCase()}
        showLineNumbers
        theme={dracula}
      />
    </pre>
  );
};

export default CodePreview;
