---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities
metadata:
  type: skill
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill
- Says "find a skill for X" or "is there a skill for X"
- Asks "can you do X" where X is a specialized capability
- Expresses interest in extending agent capabilities
- Wants to search for tools, templates, or workflows
- Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)

## What is the Skills CLI?

The Skills CLI (`npx skills`) is the package manager for the open agent skills ecosystem.

**Key commands:**

- `npx skills find [query]` - Search for skills interactively or by keyword
- `npx skills add <package>` - Install a skill from GitHub or other sources
- `npx skills check` - Check for skill updates
- `npx skills update` - Update all installed skills

**Browse skills at:** https://skills.sh/

## How to Help Users Find Skills

### Step 1: Understand What They Need

Identify the domain and specific task the user needs help with.

### Step 2: Check the Leaderboard

Check [skills.sh](https://skills.sh/) to see if well-known skills exist.

### Step 3: Search for Skills

```bash
npx skills find [query]
```

### Step 4: Verify Quality

Check install count (prefer 1K+), source reputation, and GitHub stars.

### Step 5: Present Options

Show the user the skill name, what it does, install count, and install command.

### Step 6: Offer to Install

```bash
npx skills add <owner/repo@skill> -g -y
```

## When No Skills Are Found

Offer to help directly, or suggest creating a custom skill with `npx skills init`.
