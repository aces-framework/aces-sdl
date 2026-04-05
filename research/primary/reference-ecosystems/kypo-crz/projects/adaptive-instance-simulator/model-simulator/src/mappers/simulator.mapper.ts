import {
    AccessPhase,
    AccessPhaseTask,
    InfoPhase,
    InfoPhaseTask,
    QuestionnairePhase,
    QuestionnairePhaseTask,
    Trainee,
    TrainingRunData,
    TrainingRunPathNode,
} from '@crczp/adaptive-instance-simulator/transition-visualization';
import { AbstractPhaseTypeEnum, Phase, Task, TrainingPhase } from '@crczp/training-model';

export class SimulatorMapper {
    static toCreatePathNode(task: Task, phase: TrainingPhase): TrainingRunPathNode {
        const pathNode = new TrainingRunPathNode();
        pathNode.phaseId = phase.id;
        pathNode.phaseOrder = phase.order;
        pathNode.taskId = task.id;
        pathNode.taskOrder = task.order;
        return pathNode;
    }

    /**
     * Creates default objects for transition visualization
     */

    static createTrainee(): TrainingRunData {
        const runData = new TrainingRunData();
        runData.trainee = new Trainee();
        runData.trainee.id = 1;
        runData.trainee.name = 'Trainee';
        runData.trainingRunId = 1;
        runData.trainingRunPathNodes = [];
        return runData;
    }

    static createInfoPhaseTask(): InfoPhaseTask {
        const infoTask = new InfoPhaseTask();
        infoTask.id = 0;
        infoTask.order = 0;
        infoTask.content = '';
        return infoTask;
    }

    static createQuestionnairePhaseTask(): QuestionnairePhaseTask {
        const questionnaireTask = new QuestionnairePhaseTask();
        questionnaireTask.order = 0;
        questionnaireTask.id = 0;
        questionnaireTask.questions = [];
        return questionnaireTask;
    }

    static createAccessPhaseTask(): AccessPhaseTask {
        const accessTask = new AccessPhaseTask();
        accessTask.id = 0;
        accessTask.order = 0;
        return accessTask;
    }

    static createNonTrainingPathNode(phase: Phase) {
        const pathNode = new TrainingRunPathNode();
        pathNode.phaseId = phase.id;
        pathNode.phaseOrder = phase.order;
        pathNode.taskId = 0;
        pathNode.taskOrder = 0;
        switch (phase.type) {
            case AbstractPhaseTypeEnum.Access:
                (phase as unknown as AccessPhase).tasks = [SimulatorMapper.createAccessPhaseTask()];
                break;
            case AbstractPhaseTypeEnum.Info:
                (phase as unknown as InfoPhase).tasks = [SimulatorMapper.createInfoPhaseTask()];
                break;
            case AbstractPhaseTypeEnum.Questionnaire:
                (phase as unknown as QuestionnairePhase).tasks = [SimulatorMapper.createQuestionnairePhaseTask()];
                break;
        }
        return pathNode;
    }
}
