# Git & GitHub for Hedera TradeRoot

This repo is a normal Git project. Git tracks your code history locally, and GitHub is the remote backup and collaboration copy.

## What belongs in Git

Commit source code, docs, and configuration.

Do not commit:

- database files
- API keys or `.env` files
- virtual environments
- `__pycache__` or `.pyc` files
- editor-specific local settings unless they are intentionally shared

The current `.gitignore` already covers the main local-only files for this project.

## Basic workflow

Typical daily cycle:

```bash
git status
git pull
git add <files>
git commit -m "Describe the change"
git push
```

Good commit messages are specific. Prefer `Add East Sussex audit cleanup` over `Various fixes`.

## Recommended branch workflow

For anything non-trivial, work on a branch:

```bash
git checkout -b fix/schema-docs
```

When the work is done:

```bash
git checkout main
git pull
git merge fix/schema-docs
git push
```

## Repo-specific advice

- Keep the repo outside OneDrive.
- Do not rely on `database/traderoot.db` being a portable source of truth. The schema and pipeline scripts should describe the project; local data files are disposable.
- Before running county imports, remember that `scripts/pipeline/04_import.py <county>` does a clean replace for that county and writes a backup first.
- Before committing, check that you are not staging generated review reports, backup databases, or accidental cache files.

## Before you finish a session

Run:

```bash
git status
```

If there are changes you want to keep, commit and push them before closing the session.

## Useful commands

Check current changes:

```bash
git status
git diff
```

See recent history:

```bash
git log --oneline --decorate -10
```

Discard a local change in one file only when you are certain you do not need it:

```bash
git restore path/to/file
```

Create and switch to a branch:

```bash
git checkout -b branch-name
```

Switch branches:

```bash
git checkout main
```

## Common mistakes

| Mistake | What to do |
|---|---|
| Forgot to push | Commit locally, then run `git push` |
| Committed secrets | Remove them, commit the removal, and rotate the keys |
| Seeing `__pycache__` noise | Remove tracked cache files from Git once, then let `.gitignore` keep them out |
| Working directly on `main` for risky changes | Move to a branch before the work gets larger |
| Pulling after making local edits and getting conflicts | Stop and resolve carefully instead of forcing a reset |

## VS Code note

You can do all of this either in the terminal or in the VS Code Source Control panel. The Git rules are the same either way.

