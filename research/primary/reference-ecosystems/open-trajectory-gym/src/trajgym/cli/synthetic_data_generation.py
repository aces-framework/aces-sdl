"""
CLI entry point for Synthetic Data Generation in Open Trajectory Gym.

This CLI orchestrates the generation of trajectories by leveraging the
SimulatedEnvironmentExecutor and the SyntheticGenerator.
"""

import argparse
import logging
import sys
from pathlib import Path

from ..synthetic_data_generation.generator import (
    LiteLLMAgentAdapter,
    SyntheticGenerator,
)
from ..synthetic_data_generation.manifest import WorldManifest

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open Trajectory Gym Synthetic Data Generator"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the synthetic generation manifest YAML.",
    )
    parser.add_argument(
        "--teacher-model",
        type=str,
        default="vllm_local",
        help="ID of the teacher model for orchestration.",
    )
    parser.add_argument(
        "--num-traces",
        type=int,
        default=10,
        help="Number of synthetic traces to generate.",
    )
    parser.add_argument(
        "--sft-out",
        type=str,
        default="data/synthetic_sft.jsonl",
        help="Output JSONL for SFT formatted trajectories.",
    )
    parser.add_argument(
        "--online-rl-out",
        type=str,
        default="data/synthetic_online_rl.jsonl",
        help="Output JSONL for online RL metric-ready trajectories.",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config path {args.config} does not exist.")
        sys.exit(1)

    logger.info(f"Loading WorldManifest from {args.config}")
    try:
        manifest = WorldManifest.from_yaml(str(config_path))
    except Exception as e:
        logger.error(f"Failed to parse manifest: {e}")
        sys.exit(1)

    # In a full run, we would dynamically load a whole directory of manifests
    # For this proof of concept scale, we load one and scale it up.

    logger.info("Initializing AgentAdapter and SyntheticGenerator...")
    agent_adapter = LiteLLMAgentAdapter(model_name=args.teacher_model)
    generator = SyntheticGenerator(manifests=[manifest], agent_adapter=agent_adapter)

    logger.info(f"Generating {args.num_traces} raw traces from teacher...")
    raw_traces = generator.batch_generate_traces(max_trajectories=args.num_traces)

    logger.info("Exporting to training formats...")
    generator.export_jsonl(raw_traces, args.sft_out)
    generator.export_jsonl(raw_traces, args.online_rl_out)

    logger.info(
        f"Generation successful. Output traces span {args.num_traces} completed objectives."
    )


if __name__ == "__main__":
    main()
