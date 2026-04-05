# Analysis Scripts

Utilities for analyzing RL/SFT training traces, evaluation results, and HuggingFace datasets.

## Shared Utilities

| Module | Description |
|---|---|
| `utils.py` | Common helpers: text extraction, reward/error parsing, token counting, date parsing, JSONL iteration |

## Dataset & Context Analysis

| Script | Description | Usage |
|---|---|---|
| `context_length_compare.py` | Compare context length statistics (mean, median, percentiles) across HF datasets | `python -m scripts.analysis.context_length_compare repo1 repo2 --filter 'col==val'` |
| `context_length_dist.py` | Plot context length distributions for a hardcoded list of SFT datasets | `python scripts/analysis/context_length_dist.py` |
| `solve_rate_by_context.py` | Solve/timeout/error rates binned by context length, with 3-panel plot | `python -m scripts.analysis.solve_rate_by_context repo1 repo2 --bins 0,16384,32768 --plot out.png` |
| `episode_distribution.py` | Plot episode count and tokens-per-turn distributions from HF trace datasets | `python -m scripts.analysis.episode_distribution repo1 repo2 --output out.png` |
| `filter_latest_episodes.py` | Keep only the latest episode per task in a trace dataset | `python scripts/analysis/filter_latest_episodes.py repo_id --output-jsonl out.jsonl` |
| `summarize_conversations.py` | Compute conversation stats (tokens, turns, rewards) from a JSONL file | `python scripts/analysis/summarize_conversations.py data.jsonl` |

## Training Analysis

| Script | Description | Usage |
|---|---|---|
| `parse_skyrl_metrics.py` | Parse SkyRL training logs, extract metrics and vLLM stats, generate CSV + markdown report | `python scripts/analysis/parse_skyrl_metrics.py log_folder/ output_folder/` |
| `temporal_trace_analysis.py` | Bin trace rows by timestamp to track agent improvement over training | `python scripts/analysis/temporal_trace_analysis.py repo_id --bin-hours 1` |

## Evaluation Analysis

| Script | Description | Usage |
|---|---|---|
| `eval_runtime_stats.py` | Compute runtime quantiles from eval trace result.json files | `python scripts/analysis/eval_runtime_stats.py results_dir/` |
| `trace_runtime_report.py` | Aggregate eval runtime stats with correlations and PNG visualizations | `python scripts/analysis/trace_runtime_report.py --root results_dir/` |
| `failure_mode_analysis.py` | Use GPT-5 to classify failure modes in trace datasets | `python scripts/analysis/failure_mode_analysis.py repo_id --output report.md` |
| `update_hf_failure_modes.py` | Annotate HF dataset rows with GPT-5 failure-mode summaries | `python scripts/analysis/update_hf_failure_modes.py repo_id --push` |

## Debugging & Diagnostics

| Script | Description | Usage |
|---|---|---|
| `probe_model_thinking.py` | Probe a model with real environment prompts, test thinking behavior | `python -m scripts.analysis.probe_model_thinking --model model_id` |
| `submit_probe.sh` | SLURM wrapper for `probe_model_thinking.py` | `./scripts/analysis/submit_probe.sh --model model_id --partition gpu-h100` |
| `verify_sft_thinking.py` | Test how ReasoningTemplate handles thinking blocks in SFT data | `python scripts/analysis/verify_sft_thinking.py` |
| `analyze_malformed_traces.py` | Classify malformation types in RL checkpoint traces | `python scripts/analysis/analyze_malformed_traces.py` |
| `sample_early_traces.py` | Sample malformed traces binned by timestamp to show failure evolution | `python scripts/analysis/sample_early_traces.py` |

## Batch Workflows

| Script | Description | Usage |
|---|---|---|
| `batch_filter_and_summarize.py` | Run filter + summarize across subdirectories | `python scripts/analysis/batch_filter_and_summarize.py --root dir/ --out_dir out/` |
| `batch_filter_and_summarize.sh` | Shell wrapper for the same batch workflow | `./scripts/analysis/batch_filter_and_summarize.sh root_dir/ out_dir/` |

## Dependencies

Most scripts require:
- `datasets` (HuggingFace datasets library)
- `transformers` (for tokenizers, used by context length scripts)
- `numpy`, `matplotlib` (for statistics and plotting)

Optional:
- `tiktoken` (fallback token counting in `utils.py`)
- `openai` (for GPT-5 failure mode analysis)
