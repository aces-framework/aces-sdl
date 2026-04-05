import {type editor} from 'monaco-editor';
import {useState, useEffect, useCallback} from 'react';
import {useTranslation} from 'react-i18next';
import {type EmailVariable} from 'src/models/email';

export const useEmailVariablesInEditor
= (selectedDeployment: string | undefined,
  editorInstance: editor.IStandaloneCodeEditor | undefined) => {
  const {t} = useTranslation();
  const [emailVariables, setEmailVariables] = useState<EmailVariable[]>([]);

  const defaultEmailVariables = useCallback(() => [
    {name: '{{exerciseName}}', description: t('emails.variables.exerciseName')},
  ], [t]);

  const specificDeploymentVariables = useCallback(() => [
    {name: '{{exerciseName}}', description: t('emails.variables.exerciseName')},
    {name: '{{deploymentName}}', description: t('emails.variables.deploymentName')},
    {name: '{{participantFirstName}}', description: t('emails.variables.participantFirstName')},
    {name: '{{participantLastName}}', description: t('emails.variables.participantLastName')},
    {name: '{{participantEmail}}', description: t('emails.variables.participantEmail')},
  ], [t]);

  useEffect(() => {
    if (!selectedDeployment || selectedDeployment === '') {
      setEmailVariables(defaultEmailVariables());
    } else if (selectedDeployment) {
      setEmailVariables(specificDeploymentVariables());
    }
  }, [selectedDeployment, t, defaultEmailVariables, specificDeploymentVariables]);

  const insertVariable = (variable: string) => {
    if (editorInstance) {
      const position = editorInstance.getPosition();
      if (!position) {
        return;
      }

      editorInstance.executeEdits('', [{
        range: {
          startLineNumber: position.lineNumber,
          startColumn: position.column,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        },
        text: variable,
      }]);
    }
  };

  return {emailVariables, insertVariable};
};
