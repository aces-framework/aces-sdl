interface TomlPackage {
  name: string;
  version: string;
  authors: string[];
  license: string;
  description: string;
  readme: string;
  categories: string[];
  type: string;
}

interface Preview {
  type: 'picture' | 'video' | 'code';
  value: string[];
}

interface Content {
  type:
    | 'VM'
    | 'Feature'
    | 'Condition'
    | 'Inject'
    | 'Event'
    | 'Malware'
    | 'Exercise'
    | 'Banner'
    | 'Other';
  categories: string[];
  preview: Preview[];
}

export interface Project {
  package: TomlPackage;
  content: Content;
}
