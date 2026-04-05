# ONLINE_RL Base Configs

These are **base template configs** for SkyRL ONLINE_RL training. They are NOT
user-facing — the actual training config is built programmatically by
`src/trajgym/training/online_rl/runtime.py` from `examples/<model>/training.yaml`.

Each file here provides SkyRL-native defaults (trainer, generator, environment
sections) for a specific model architecture. The runtime merges these with
user config at launch time.
