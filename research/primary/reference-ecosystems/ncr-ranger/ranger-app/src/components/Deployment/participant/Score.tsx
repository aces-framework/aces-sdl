import React from 'react';
import DeploymentDetailsGraph from 'src/components/Scoring/Graph';
import TloTable from 'src/components/Scoring/TloTable';
import {type ScoringMetadata} from 'src/models/scenario';
import {type Score} from 'src/models/score';

const ParticipantScore = ({
  scoringData, scores}: {scoringData: ScoringMetadata | undefined; scores: Score[] | undefined;
}) => (
  <div>
    <div className='py-8'>
      <TloTable
        scoringData={scoringData}
        scores={scores}
        tloMap={scoringData?.tlos}
      />
    </div>
    <DeploymentDetailsGraph
      colorsByRole
      scoringData={scoringData}
      scores={scores}
    />
  </div>
);

export default ParticipantScore;
