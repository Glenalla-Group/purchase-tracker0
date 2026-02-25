# Git Workflow Examples - CI Behavior

This document shows how different Git commands trigger CI builds with the current workflow configuration.

## Workflow Behavior Summary

- ✅ **PR opened** → CI runs (validates PR)
- ❌ **PR merged** → CI skipped (already validated)
- ✅ **Direct push to main/develop** → CI runs
- ❌ **Push to feature branch** → No CI (unless PR is opened)

---

## Scenario 1: Create a Pull Request (CI RUNS ✅)

```bash
# 1. Create a feature branch
git checkout -b feature/fix-playwright-issue

# 2. Make your changes
# ... edit files ...

# 3. Commit changes
git add backend/Dockerfile
git commit -m "fix: Remove Playwright from Dockerfile"

# 4. Push to remote
git push origin feature/fix-playwright-issue

# 5. Open PR on GitHub (via web UI or GitHub CLI)
gh pr create --base main --head feature/fix-playwright-issue --title "fix: Playwright issue"
```

**Result:** ✅ CI runs (Backend CI - Build and Push to ECR #24)

---

## Scenario 2: Merge Pull Request (CI SKIPPED ❌)

```bash
# Option A: Merge via GitHub web UI
# Click "Merge pull request" button

# Option B: Merge via GitHub CLI
gh pr merge 6 --merge

# Option C: Merge locally and push
git checkout main
git pull origin main
git merge feature/fix-playwright-issue
git push origin main
```

**Result:** ❌ CI skipped (merge commit detected, PR was already validated)

**Note:** The merge commit message will be: `"Merge pull request #6 from user/feature/fix-playwright-issue"`

---

## Scenario 3: Direct Push to Main (CI RUNS ✅)

```bash
# Direct commit to main (hotfix scenario)
git checkout main
git pull origin main

# Make urgent fix
# ... edit files ...

git add backend/settings.py
git commit -m "fix: Critical production bug"
git push origin main
```

**Result:** ✅ CI runs (not a merge commit, so build executes)

---

## Scenario 4: Push to Feature Branch Without PR (NO CI ❌)

```bash
# Push to feature branch
git checkout -b feature/new-feature
# ... make changes ...
git add .
git commit -m "feat: Add new feature"
git push origin feature/new-feature
```

**Result:** ❌ No CI (workflow only triggers on main/develop branches or PRs)

---

## Scenario 5: Update Existing PR (CI RUNS ✅)

```bash
# Make additional changes to your PR branch
git checkout feature/fix-playwright-issue
# ... make more changes ...
git add .
git commit -m "fix: Additional improvements"
git push origin feature/fix-playwright-issue
```

**Result:** ✅ CI runs again (PR updated, re-validates)

---

## Scenario 6: Squash Merge (CI SKIPPED ❌)

```bash
# Squash merge via GitHub web UI
# Click "Squash and merge" button

# Or via GitHub CLI
gh pr merge 6 --squash
```

**Result:** ❌ CI skipped (squash merge creates commit with "Merge pull request" in message)

---

## Scenario 7: Rebase Merge (CI SKIPPED ❌)

```bash
# Rebase merge via GitHub web UI
# Click "Rebase and merge" button

# Or via GitHub CLI
gh pr merge 6 --rebase
```

**Result:** ❌ CI skipped (rebase merge also creates merge commit)

---

## Testing the Workflow Locally

You can test what commit messages trigger CI by checking the commit message:

```bash
# Check if current commit is a merge commit
git log -1 --pretty=%B | grep -q "Merge pull request" && echo "Merge commit - CI will skip" || echo "Regular commit - CI will run"

# View recent commit messages
git log --oneline -5
```

---

## Common Workflow Patterns

### Standard Feature Development
```bash
# 1. Create branch
git checkout -b feature/my-feature

# 2. Develop and commit
git add .
git commit -m "feat: Add feature"
git push origin feature/my-feature

# 3. Open PR → CI runs ✅

# 4. After review, merge PR → CI skipped ❌ (already validated)
```

### Hotfix Workflow
```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix

# 2. Fix and commit
git add .
git commit -m "fix: Critical production issue"
git push origin hotfix/critical-fix

# 3. Open PR → CI runs ✅

# 4. Merge PR → CI skipped ❌

# 5. If direct push needed (bypass PR):
git checkout main
git merge hotfix/critical-fix
git push origin main  # → CI runs ✅ (direct push, not merge commit)
```

---

## Troubleshooting

### Why is CI still running after merge?

Check the commit message:
```bash
git log -1 --pretty=%B
```

If it doesn't contain "Merge pull request", the condition won't match. This can happen if:
- Using a custom merge strategy
- Manually creating merge commits with different messages
- Using `--no-ff` flag with custom message

### Force CI to run after merge

If you need CI to run after a merge, you can:
1. Use `workflow_dispatch` to manually trigger
2. Push an empty commit: `git commit --allow-empty -m "chore: Trigger CI" && git push`

---

## Summary Table

| Git Action | CI Runs? | Reason |
|------------|----------|--------|
| Open PR | ✅ Yes | PR validation needed |
| Merge PR (standard) | ❌ No | Already validated in PR |
| Merge PR (squash) | ❌ No | Merge commit detected |
| Merge PR (rebase) | ❌ No | Merge commit detected |
| Direct push to main | ✅ Yes | Not a merge commit |
| Push to feature branch | ❌ No | Not main/develop, no PR |
| Update existing PR | ✅ Yes | Re-validation needed |
| Manual workflow_dispatch | ✅ Yes | Explicit trigger |

