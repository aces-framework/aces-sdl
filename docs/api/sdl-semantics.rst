SDL Semantics
=============

The ``aces_sdl.semantics`` subpackage holds SDL-language semantic rules —
objective-window analysis, the workflow step-type contract, branch closure, and
the (pure) workflow step-result validator — used by the SDL validator, by the
processor at compile time, and by the processor runtime.

Per ADR-015 these helpers live with the SDL package because ``aces_sdl``
defines the language; they depend only on the standard library and have no
import-time coupling to ``aces_processor``.

.. currentmodule:: aces_sdl.semantics

Objective Semantics
-------------------

.. automodule:: aces_sdl.semantics.objectives
   :members:

Workflow Semantics
------------------

.. automodule:: aces_sdl.semantics.workflow
   :members:
