"""Processor-runtime reconciliation helpers (planner).

Per ADR-015, the SDL-language semantic helpers — objective-window analysis,
the workflow step-type contract, ``branch_closure``, and the (pure) workflow
step-result validator — live in ``aces_sdl.semantics``. ``planner`` stays
here: it reconciles compiled resources against runtime snapshots, which is
processor-runtime logic over a processor artifact, not SDL-language semantics.
"""
