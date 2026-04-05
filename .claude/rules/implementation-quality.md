---
paths:
  - "backend/src/**/*.java"
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
---

## Implementation Standards

- Never take shortcuts. Implement features properly and completely.
  You are not under time pressure. You operate at 200x human coding
  speed. There is no reason to cut corners, use placeholder
  implementations, or defer work.

- Never recommend deferring a fix or improvement "for later" or
  "in a follow-up". If something is broken or missing, fix it now.
  Tech debt has zero justification when the fix is within reach.

- Always check your implementation against the full requirement
  statement clause by clause before declaring completion.

- When you encounter an architectural decision, prefer the approach
  that follows existing patterns in the codebase over inventing
  something new. Read surrounding code first.

- Do not add unnecessary abstractions, indirection layers, or
  "extensibility" that isn't required by the current task. Three
  similar lines of code are better than a premature abstraction.

- Do not create stub or placeholder implementations that "will be
  filled in later." Either implement it fully or don't create it.
