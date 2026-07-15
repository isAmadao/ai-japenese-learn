---
name: skill-creator
description: Create a new Claude Code skill — guides through name, description, behavior, and file generation
metadata:
  type: skill
---

# Skill Creator

Guides the user through creating a new Claude Code skill and writes the skill file.

## Usage

```
/skill-creator
```

## Process

1. **Ask the user** what the skill should do — one sentence use case
2. **Determine the skill type**:
   - **Prompt-based** (most skills) — `.md` file in `.claude/skills/`; Claude reads it when invoked
   - **Command-based** (rare) — registered in `.claude/settings.local.json` with a shell command
3. **Choose a name** — short kebab-case (e.g. `deploy-check`, `format-code`)
4. **Write the skill file** to `.claude/skills/<name>.md` with frontmatter:
   ```yaml
   ---
   name: <kebab-case-name>
   description: <one-line summary — shown in the available-skills list>
   metadata:
     type: skill
   ---

   # <Title>

   <full instructions Claude should follow when this skill is invoked>
   ```
5. **For command-based skills only**: register in `.claude/settings.local.json`

## Rules

- `name:` in frontmatter must match the filename (without `.md`)
- `description:` is what the user sees in the skill list — make it clear and actionable
- The body is written for Claude to read (not the user), so use imperative tone
- Put the user-facing `## Usage` section early so Claude can show it
- If the skill needs arguments, document them under Usage with examples

## Example

When creating a "check-deploy" skill, the file looks like:

```markdown
---
name: check-deploy
description: Check production deploy status — health, recent errors, and version
metadata:
  type: skill
---

# Check Deploy

Check the current production deployment for health, recent errors, and version info.

## Usage

```
/check-deploy [env]
```

## Instructions

1. Call the deploy health endpoint
2. Check for recent error spikes
3. Report current version vs latest
```
