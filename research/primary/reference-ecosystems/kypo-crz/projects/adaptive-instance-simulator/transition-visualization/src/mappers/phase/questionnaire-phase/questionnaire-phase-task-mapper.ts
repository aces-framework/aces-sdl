import { AdaptiveQuestion } from '../../../model/phase/questionnaire-phase/adaptive-question';
import { QuestionnairePhaseDTO } from '../../../dto/phase/questionnaire-phase/questionnaire-phase-dto';
import { QuestionnairePhaseTask } from '../../../model/phase/questionnaire-phase/questionnaire-phase-task';
import { QuestionDTO } from '../../../dto/phase/questionnaire-phase/question-dto';
import { QuestionTypeEnum } from '../../../model/enums/question-type.enum';
import { ChoiceDTO } from '../../../dto/phase/questionnaire-phase/choice-dto';
import { Choice } from '../../../model/phase/questionnaire-phase/choice';
import { QuestionnaireTypeEnum } from '../../../model/enums/questionnaire-type.enum';

export class QuestionnairePhaseTaskMapper {
    static fromDTO(dto: QuestionnairePhaseDTO): QuestionnairePhaseTask {
        const result = new QuestionnairePhaseTask();
        result.id = 0;
        result.order = 0;
        switch (dto.questionnaire_type) {
            case 'ADAPTIVE': {
                result.questionnaireType = QuestionnaireTypeEnum.Adaptive;
                break;
            }
            case 'GENERAL': {
                result.questionnaireType = QuestionnaireTypeEnum.General;
                break;
            }
        }
        if (dto.questions === undefined || dto.questions === null) {
            result.questions = [];
        } else {
            result.questions = this.mapQuestionsFromDTO(dto.questions).sort((a, b) => a.order - b.order);
        }
        return result;
    }

    private static mapQuestionsFromDTO(questions: QuestionDTO[]): AdaptiveQuestion[] {
        const result: AdaptiveQuestion[] = [];
        questions.forEach((questionDTO) => {
            const question = new AdaptiveQuestion();
            question.id = questionDTO.id;
            question.order = questionDTO.order;
            question.text = questionDTO.text;
            question.choices = this.mapChoicesFromDTO(questionDTO.choices).sort((a, b) => a.order - b.order);
            switch (questionDTO.question_type) {
                case 'FFQ': {
                    question.questionType = QuestionTypeEnum.FFQ;
                    break;
                }
                case 'MCQ': {
                    question.questionType = QuestionTypeEnum.MCQ;
                    break;
                }
                case 'RFQ': {
                    question.questionType = QuestionTypeEnum.RFQ;
                    break;
                }
            }
            result.push(question);
        });
        return result;
    }

    private static mapChoicesFromDTO(choices: ChoiceDTO[]): Choice[] {
        const result: Choice[] = [];
        choices.forEach((choiceDto) => {
            const choice = new Choice();
            choice.id = choiceDto.id;
            choice.order = choiceDto.order;
            choice.text = choiceDto.text;
            choice.correct = choiceDto.correct;
            result.push(choice);
        });
        return result;
    }
}
