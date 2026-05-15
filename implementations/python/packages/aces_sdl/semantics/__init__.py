"""SDL-language semantic rules (objective windows, workflow step contracts).

Per ADR-015, these helpers live with the SDL package: ``aces_sdl/validator.py``
uses them, and they have no processor-runtime dependencies. The processor's
own reconciliation helpers stay at ``aces_processor.semantics.planner``.
"""
