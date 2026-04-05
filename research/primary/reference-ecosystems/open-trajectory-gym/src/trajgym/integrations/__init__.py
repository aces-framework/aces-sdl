"""Framework-specific integrations (BoxPwnr, etc.).

Each module here wraps an external framework to satisfy Open Trajectory Gym protocols.
These are leaf modules — lazy-imported only by CLI/eval code that needs them.
The core training pipeline (Online RL, SFT, rewards, envs) never touches these.

For subprocess-based BYO agent adapters, see examples/bring-your-own/agent/.
"""
