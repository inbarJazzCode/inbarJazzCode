# GIT AND ROLLBACK

## Branch & commits (this run)

- **Branch:** `claude/new-session-z4iq3g`
- **HEAD:** `93ceb5c` (docs commit)

```
93ceb5c docs: README, architecture, security review and PyInstaller packaging
7f5c282 test: deterministic offline suite plus smoke test and synthetic fixture
7bcd7c1 feat: shared service layer, unified launcher, Streamlit and desktop UIs
f4bdc1a feat: generalize market data to provider-supported assets with offline fallback
c357ec3 feat: versioned SQLite persistence with migrations, backup and integrity
9dc0219 feat: statistical modeling lab (OLS, logistic, Poisson, optim, evaluation)
a154738 chore: project scaffolding, gitignore and dependencies
```

The repository had **no prior commits**; these are the initial history.

## Rollback

Because the repository started empty, rolling back removes newly-added files
only — there is no prior user work to lose.

```bash
# Undo the most recent commit but keep the files staged:
git reset --soft HEAD~1

# Return to a specific earlier commit (keeps working tree):
git reset --mixed 9dc0219

# Discard everything back to before this run (empty tree):
git update-ref -d HEAD        # removes the branch pointer; files remain on disk
```

To roll back **only** a database schema migration, restore a backup:

```bash
python main.py backup    # (creates one first if needed)
# copy backups/statinvest.<UTC>.bak over the live statinvest.db
```

## Push / PR

The branch was pushed to `inbarJazzCode/inbarJazzCode` (which is **public**).
Creating a new **private** repo and opening a PR could not be completed from
this session (the token is scoped to the single existing repo; repo creation and
branch deletion returned HTTP 403). **See `REMOTE_STATUS.md` for the exact
commands to create the private repo, push there, and remove the work from the
public profile repo.** The ZIP in this folder is the primary, self-contained
handoff artifact.
