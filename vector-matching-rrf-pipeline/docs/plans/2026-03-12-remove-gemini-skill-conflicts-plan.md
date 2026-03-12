# Remove Gemini Skill Conflicts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove conflicting Gemini skill directories from `~/.gemini/skills/` to prioritize the CLI extension versions.

**Architecture:** Use shell commands to remove specific directories while preserving the user-requested `code-reviewer` skill.

**Tech Stack:** Bash

---

### Task 1: Identify and Remove Conflicting Skills

**Files:**
- Modify: `/usr/local/google/home/pmgraham/.gemini/skills/` (Remove directories)

**Step 1: Verify current state**

Run: `ls -la /usr/local/google/home/pmgraham/.gemini/skills/`
Expected: See all skill directories including `brainstorming`, `using-superpowers`, `code-reviewer`, etc.

**Step 2: Remove conflicting directories**

Run:
```bash
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/brainstorming
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/dispatching-parallel-agents
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/executing-plans
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/finishing-a-development-branch
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/receiving-code-review
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/requesting-code-review
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/subagent-driven-development
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/systematic-debugging
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/test-driven-development
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/using-git-worktrees
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/using-superpowers
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/verification-before-completion
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/writing-plans
rm -rf /usr/local/google/home/pmgraham/.gemini/skills/writing-skills
```

**Step 3: Verify remaining skills**

Run: `ls -la /usr/local/google/home/pmgraham/.gemini/skills/`
Expected: Only `.` `..` and `code-reviewer` should remain.

**Step 4: Commit the design docs**

Run:
```bash
git add docs/plans/2026-03-12-remove-gemini-skill-conflicts.md docs/plans/2026-03-12-remove-gemini-skill-conflicts-plan.md
git commit -m "docs: add design and plan for removing gemini skill conflicts"
```
