## Review Fix Standards

- Fix ALL issues found during code review and security review.
  Do not categorize issues as "defer" or "low priority" to avoid
  doing work. If the fix is straightforward, do it.

- Never recommend deferring fixes because of "time constraints",
  "scope", or "follow-up PRs". You are an LLM. You do not have
  time constraints. Just do the work.

- The only valid reason to stop and consult the user is if a fix
  would require a significant architectural change that could break
  other features. "Significant" means touching 5+ files outside the
  current feature scope.

- Do not surface nitpicks about PR titles or descriptions unless
  they are grossly misleading.
