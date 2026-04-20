# Git & GitHub with PyCharm — A Practical Guide

*Written from real experience building the Hedera TradeRoot project.*

---

## What is Git and why does it matter?

Git is a version control system — it tracks every change you make to your code over time. Think of it as a detailed save history where you can go back to any previous version, see exactly what changed and when, and safely experiment without breaking working code.

GitHub is where your Git history lives in the cloud — it's your backup, your portfolio, and (eventually) how you collaborate with others.

---

## Key concepts

### The three states of your code

1. **Your files** — the actual code sitting on your machine
2. **A commit** — a labelled snapshot of your files at a point in time, stored locally
3. **GitHub** — the cloud where your snapshots are backed up and shared

### Commit vs Push

This is the most important distinction to understand:

- **Commit** — takes a snapshot of your changes and saves it *locally* on your machine. GitHub doesn't know about it yet.
- **Push** — sends your local commits up to GitHub so they're backed up and visible to others.

A good analogy: committing is like taking a photo and putting it in a local album on your desk. Pushing is like uploading that photo to a shared cloud album.

> **Always commit and push before closing your Codespace or ending a session.**

### The .gitignore file

A `.gitignore` file tells Git which files to ignore and never commit. Common entries:

```
*.db          # Database files (may contain sensitive data)
.venv/        # Python virtual environment (large, reproducible)
.idea/        # PyCharm project files (machine-specific)
__pycache__/  # Python cache files
.env          # Environment variables (may contain secrets)
```

> **Rule of thumb:** Code goes to GitHub. Data and secrets stay local.

---

## Setting up a project in PyCharm

### Cloning an existing repository

1. Open PyCharm
2. **File → New Project**
3. Set the location to your projects folder (e.g. `C:\Projects\hedera-traderoot`)
4. PyCharm will detect the existing `.git` folder and set up Git integration automatically
5. It will show **"Git has been installed"** — this means PyCharm has connected to the repo

> **Don't use OneDrive for Git repos.** OneDrive and Git can conflict — OneDrive tries to sync files while Git is writing them. Keep your projects in a plain folder like `C:\Projects\`.

### Cloning via GitHub Desktop

If you don't have Git installed on your machine, GitHub Desktop is a good alternative:

1. Open GitHub Desktop
2. **File → Clone repository → URL tab**
3. Enter your repo URL (e.g. `https://github.com/DrJSaint/hedera-traderoot.git`)
4. Set local path to `C:\Projects`
5. Click **Clone**

> **Important:** Create `C:\Projects` first in File Explorer — Git creates the repo folder inside it, but the parent folder must already exist.

---

## Day-to-day workflow in PyCharm

### Making and committing changes

1. Edit your files in PyCharm
2. Press `Ctrl+K` to open the commit dialog
3. You'll see all changed files listed — tick the ones you want to include
4. Write a **meaningful commit message** in the Summary box
5. Click **Commit and Push** to commit locally AND push to GitHub in one step

> **Write good commit messages.** "Various fixes" is not useful. "Add delete confirmation dialog" tells you exactly what changed. You'll thank yourself later.

### What the colour coding means

In the file explorer and editor, PyCharm shows Git status with colours:
- **Blue** = modified since last commit
- **Green** = new file not yet committed
- **Red** = unversioned (not tracked by Git at all)
- Blue bar in editor margin = modified line

### Pulling changes from GitHub

If you've made changes on GitHub directly (e.g. editing the README in the browser), or if someone else has pushed changes, you need to pull them down:

**Git → Update Project** (or `Ctrl+T`)

This is PyCharm's way of doing `git pull`.

---

## Branching

Branches let you develop new features without touching your stable working code.

### Why branch?

- Your `main` branch is what's deployed and working
- You want to try something experimental or do a big restructure
- If it goes wrong, `main` is untouched

### Creating a branch

1. Click the branch name in the top bar (e.g. `main`)
2. Select **New Branch**
3. Give it a descriptive name (e.g. `mobile-ui`, `auth-feature`)
4. Leave **Checkout branch** ticked — this switches you to the new branch immediately

### Working on a branch

Everything is the same — edit, commit, push. Your commits go to the feature branch, not `main`.

### Merging back into main

When you're happy with your feature branch:

1. Click the branch name in the top bar
2. Find `main` in the list and click **Checkout** to switch to it
3. Click the branch name again
4. Find your feature branch in the list
5. Select **Merge 'mobile-ui' into 'main'**
6. Push with `Ctrl+Shift+K` to send the merged code to GitHub

Or in the terminal:
```bash
git checkout main
git merge mobile-ui
git push
```

### Deleting a branch

Once merged, you can tidy up:

1. Click the branch name
2. Find the branch
3. Select **Delete**

---

## Working with Codespaces

GitHub Codespaces gives you a cloud development environment — a Linux machine in the browser. This is particularly useful for teaching because students don't need to install anything locally.

### Closing down a Codespace — always do this in order

1. `Ctrl+C` in the terminal to stop your app (e.g. Streamlit)
2. Commit and push your changes:
```bash
git add .
git commit -m "Brief description of what you changed"
git push origin main
```
3. Close the browser tab

> **Why this matters:** Changes inside a Codespace only exist there until you push to GitHub. If the Codespace stops before you push, you could lose work. GitHub auto-stops Codespaces after 30 minutes of inactivity.

### Reopening a Codespace

Go to your repo on GitHub → green **Code** button → **Codespaces** tab → click your Codespace name.

### Students and Codespaces

Students don't need to clone anything locally. They just:
1. Go to the repo on GitHub
2. Click the green **Code** button → **Codespaces** tab
3. Click **Create codespace on main**

Everything runs in the browser. No installation, no admin rights, no "works on my machine" problems.

> **Note on data:** Anything created inside a Codespace that isn't committed to GitHub will eventually disappear. Code files, CSVs, notebooks — commit them regularly. SQLite databases are rebuilt via the init script.

---

## Deployment with Streamlit Cloud

Once your app is on GitHub, deploying to Streamlit Community Cloud is straightforward:

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. **Create app → Deploy a public app from GitHub**
4. Set:
   - Repository: `username/repo-name`
   - Branch: `main`
   - Main file path: `app/main.py`
   - App URL: `your-app-name`
5. Click **Deploy**

Streamlit Cloud automatically redeploys every time you push to the watched branch. No manual steps needed — just push and wait a minute or two.

---

## Common mistakes and how to fix them

| Mistake | Fix |
|---|---|
| Forgot to write a commit message | PyCharm won't let you commit without one — it'll prompt you |
| Committed to the wrong branch | Use `git cherry-pick` or just redo the change on the right branch |
| Pushed sensitive data (passwords, API keys) | Remove from file, commit the removal, consider the key compromised and rotate it |
| `.idea/` files showing as unversioned | Add `.idea/` to `.gitignore` |
| OneDrive conflicts | Move your repo outside OneDrive |
| "Cannot find path" when running `cd` | The folder doesn't exist yet — create it first in File Explorer |
| Pasting code with wrong indentation in VS Code | Use **Edit → Paste and Indent** or select pasted lines and press Tab |

---

## Quick reference

| Action | PyCharm shortcut | Terminal equivalent |
|---|---|---|
| Commit | `Ctrl+K` | `git commit -m "message"` |
| Push | `Ctrl+Shift+K` | `git push` |
| Pull | `Ctrl+T` | `git pull` |
| New branch | Branch menu → New Branch | `git checkout -b branch-name` |
| Switch branch | Branch menu → Checkout | `git checkout branch-name` |
| Merge branch | Branch menu → Merge | `git merge branch-name` |

