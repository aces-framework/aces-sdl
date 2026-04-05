import {useState, useEffect, useCallback} from 'react';
import type {Scenario} from 'src/models/scenario';
import init, {
  parse_and_verify_sdl as parseAndVerifySDL,
} from '@open-cyber-range/wasm-sdl-parser';
import byteSize from 'byte-size';

type ResourceEstimation = {
  totalRam: string | undefined;
  totalCpu: number | undefined;
  resourceEstimationError: string | undefined;
};

const useResourceEstimation = (sdlSchema: string | undefined): ResourceEstimation => {
  const [totalRam, setTotalRam] = useState<string | undefined>(undefined);
  const [totalCpu, setTotalCpu] = useState<number | undefined>(undefined);
  const [resourceEstimationError, setResourceEstimationError]
  = useState<string | undefined>(undefined);
  const [isInitialized, setIsInitialized] = useState<boolean>(false);

  const estimateResources = useCallback(async (inputSdlSchema: string | undefined) => {
    if (!inputSdlSchema) {
      return;
    }

    if (!isInitialized) {
      await init();
      setIsInitialized(true);
    }

    let ram = 0;
    let cpu = 0;

    try {
      const parsedSdl = parseAndVerifySDL(inputSdlSchema);
      const scenario = JSON.parse(parsedSdl) as Scenario;

      if (scenario?.infrastructure && scenario?.nodes) {
        for (const nodeName of Object.keys(scenario.infrastructure)) {
          const infraNode = scenario.infrastructure[nodeName];
          const nodeCount = infraNode.count;
          const node = scenario.nodes?.[nodeName];

          if (node?.resources) {
            ram += node.resources.ram * nodeCount;
            cpu += node.resources.cpu * nodeCount;
          }
        }
      }

      const formattedRam = byteSize(ram, {units: 'iec', precision: 1});
      setTotalRam(`${formattedRam.value} ${formattedRam.unit}`);
      setTotalCpu(cpu);
      setResourceEstimationError(undefined);
    } catch (error) {
      if (typeof error === 'string') {
        setResourceEstimationError(`SDL Parsing error: ${error}`);
      } else {
        setResourceEstimationError('SDL Parsing error');
      }

      setTotalRam(undefined);
      setTotalCpu(undefined);
    }
  }, [isInitialized]);

  useEffect(() => {
    try {
      void estimateResources(sdlSchema);
    } catch (error) {
      if (error instanceof Error) {
        setResourceEstimationError(`Error estimating resources: ${error.message}`);
      } else {
        setResourceEstimationError('Error estimating resources');
      }

      setTotalRam(undefined);
      setTotalCpu(undefined);
    }
  }, [sdlSchema, estimateResources]);

  return {totalRam, totalCpu, resourceEstimationError};
};

export default useResourceEstimation;
