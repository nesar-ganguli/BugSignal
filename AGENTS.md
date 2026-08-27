# BugSignal repository instructions

## Current implementation documentation

`docs/CURRENT_IMPLMENTATION.MD` is the repository's living implementation map for humans and LLM-based coding agents.

Every change that adds or changes a feature, runtime flow, API, workflow state, data model, dependency, configuration value, security boundary, operational requirement, or important limitation must update `docs/CURRENT_IMPLMENTATION.MD` in the same change. Keep its "Last verified" date and relevant sections current. Pure formatting, comment-only, or test-only changes that do not alter documented behavior do not require an update.

Before completing an implementation change:

1. Read `docs/CURRENT_IMPLMENTATION.MD` before editing behavior.
2. Update the document to describe the resulting implementation, not the intended future design.
3. Keep links and file paths valid and distinguish automated, manual, legacy, and planned behavior.
4. If the change exposes a new caveat or unresolved mismatch, record it under "Current limitations and sharp edges."

