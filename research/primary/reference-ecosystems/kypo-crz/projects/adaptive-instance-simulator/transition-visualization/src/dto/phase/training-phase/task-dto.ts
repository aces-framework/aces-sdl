export interface TaskDTO {
    id: number;
    title: string;
    order: number;
    answer: string;
    content: string;
    solution: string;
    incorrect_answer_limit: number;
    modify_sandbox: boolean;
    sandbox_change_expected_duration: number;
}
