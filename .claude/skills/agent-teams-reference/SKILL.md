---
name: agent-teams-reference
description: Reference documentation for Claude Code Agent Teams. Read this before creating or managing agent teams.
disable-model-invocation: true
---

# Claude Code Agent Teams — Quick Reference

## Official Documentation
- Agent Teams: https://code.claude.com/docs/en/agent-teams
- Subagents: https://code.claude.com/docs/en/sub-agents
- Skills: https://code.claude.com/docs/en/skills
- Best Practices: https://code.claude.com/docs/en/best-practices

## Display Modes
- **in-process** (default): All teammates in one terminal. Shift+Down cycles between them.
- **split panes**: Each teammate gets its own tmux pane. Requires tmux session.
- **auto** (recommended): Uses split panes if inside tmux, otherwise in-process.

## Working with cmux + tmux
cmux is a native macOS terminal app. tmux runs as a process inside cmux panes.
1. Open cmux, create a workspace tab for the project
2. In the cmux pane, start a tmux session: `tmux new-session -s fulcrum`
3. Launch Claude Code inside tmux: `claude`
4. Agent teams will auto-detect tmux and use split panes

## Key Commands During Team Execution
- **Shift+Down**: Cycle through teammates (in-process mode)
- **Click pane**: Interact with specific teammate (split-pane mode)
- **Type to teammate**: Give additional instructions directly
- **Tell lead to wait**: If lead finishes early, instruct it to wait for all teammates

## Common Issues
- **Permission prompts blocking teammates**: Pre-approve operations via `/allowed-tools`
- **Teammate stopping on error**: Check output, give instructions, or spawn replacement
- **Orphaned tmux sessions**: `tmux ls` then `tmux kill-session -t <n>`
- **Lead shutting down early**: Tell lead explicitly to wait for all teammates

## Superpowers Integration
The Superpowers plugin provides:
- `/superpowers:brainstorm` — Interactive design refinement before coding
- `/superpowers:write-plan` — Generate implementation plan from brainstorm output
- `/superpowers:execute-plan` — Execute plan with subagent-driven development + code review

Workflow: brainstorm → write-plan → either execute-plan (subagents) OR fulcrum-agent-team (full teams)
