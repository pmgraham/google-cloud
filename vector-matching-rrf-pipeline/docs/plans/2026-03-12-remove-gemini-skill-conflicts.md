# Design Doc: Remove Gemini Skill Conflicts

## Problem
The user installed a new Gemini CLI extension (`superpowers`), but existing skills in `~/.gemini/skills/` are overriding the extension's skills, causing conflict warnings and potentially using outdated skill versions.

## Proposed Change
Remove the duplicate skill directories from `~/.gemini/skills/` to allow the extension skills to take precedence.

### Skills to be removed from `~/.gemini/skills/`:
- brainstorming
- dispatching-parallel-agents
- executing-plans
- finishing-a-development-branch
- receiving-code-review
- requesting-code-review
- subagent-driven-development
- systematic-debugging
- test-driven-development
- using-git-worktrees
- using-superpowers
- verification-before-completion
- writing-plans
- writing-skills

### Skills to be kept:
- code-reviewer (requested by user)

## Implementation Plan
1. Execute `rm -rf` on each of the conflicting directories in `/usr/local/google/home/pmgraham/.gemini/skills/`.
2. Verify that `code-reviewer` remains.
3. Verify that the conflict warnings are resolved (by listing the remaining skills).

## Verification
- Run `ls -la /usr/local/google/home/pmgraham/.gemini/skills/` to confirm only `code-reviewer` and the directory itself remain.
