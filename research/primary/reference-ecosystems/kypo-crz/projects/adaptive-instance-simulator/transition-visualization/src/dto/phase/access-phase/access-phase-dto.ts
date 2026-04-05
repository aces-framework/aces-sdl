import { AbstractPhaseDTO } from '../abstract-phase-dto';

export interface AccessPhaseDTO extends AbstractPhaseDTO {
    cloud_content: string;
    local_content: string;
}
