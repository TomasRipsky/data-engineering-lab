---
name: new-project
description: Start a new data engineering project in this lab — checks the stack is industry-standard, creates the GitHub issue, branch from dev, copies projects/_template (README, docs/guide.md, docs/design/, docs/decisions/), renames the package, registers it in the README and vault, and opens a PR. Use when Tomas asks to start, create or bootstrap a project.
---

# New project

## 1. Name (validate before touching GitHub)
Ask for (or confirm) a kebab-case name and a one-line pitch.
```bash
[[ "$NAME" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]] || { echo "invalid name: $NAME"; exit 1; }
PKG="${NAME//-/_}"
python3 -c "import keyword,sys; n=sys.argv[1]; sys.exit(keyword.iskeyword(n) or n in sys.stdlib_module_names)" "$PKG" \
  || { echo "$PKG clashes with a Python keyword or stdlib module"; exit 1; }
[[ -e "projects/$NAME" ]] && { echo "projects/$NAME already exists"; exit 1; }
```
Also reject names equal to a planned dependency (e.g. `pytest`, `pandas`) — ask Tomas for another.

## 1b. Industry-standard check
For the intended core stack (ingestion, storage, transformation, orchestration, serving), state the market signal of each choice in one line: job-market demand and adoption. Sources: vault `08 - Research/Market Signals 2026.md` and `lab/tech-radar.md`; check current signals (web) when a tech is not there. A niche choice needs an explicit reason Tomas accepts — it becomes an ADR in the project's `docs/decisions/`. If a tech enters Trial, update `lab/tech-radar.md` in the project's PR.

## 2. Issue and branch
```bash
git switch dev && git pull --ff-only
gh label create "project:$NAME" --color 0E8A16 --description "Project $NAME" 2>/dev/null || true
URL=$(gh issue create --title "feat($NAME): bootstrap project" \
  --label "type:feat,project:$NAME" \
  --body "Bootstrap \`projects/$NAME\` from the template. Pitch: $PITCH") || { echo "issue creation failed"; exit 1; }
ISSUE=${URL##*/}
[[ "$ISSUE" =~ ^[0-9]+$ ]] || { echo "unexpected gh output: $URL"; exit 1; }
git switch -c "feat/$ISSUE-$NAME-bootstrap"
```

## 3. Copy and rename
```bash
rsync -a --exclude .venv --exclude .pytest_cache --exclude .ruff_cache --exclude uv.lock \
  projects/_template/ "projects/$NAME/"
mv "projects/$NAME/src/template_project" "projects/$NAME/src/$PKG"
grep -rl --exclude-dir=.venv -e template-project -e template_project -e '# Project Name' "projects/$NAME" \
  | xargs perl -pi -e "s/template-project/$NAME/g; s/template_project/$PKG/g; s/^# Project Name\$/# $NAME/; s/^# Project Name — /# $NAME — /"
```
Then fill the placeholders with the Edit tool (not sed — the pitch may contain `/`, `&` or `|`):
- `projects/$NAME/README.md`: the `> One-sentence pitch...` line → `> $PITCH`.
- `projects/$NAME/pyproject.toml`: `description = "..."` → the pitch.
- `projects/$NAME/src/$PKG/__init__.py`: docstring → `"""$NAME: <pitch>."""`.

```bash
(cd "projects/$NAME" && uv sync && uv run pytest && uv run ruff check .)
```
All three must pass before continuing.

## 4. Register
- Append a row to the `## Projects` table in the root `README.md` (escape `|` in the pitch as `\|`): `| [$NAME](projects/$NAME/) | $PITCH | TBD | 🌱 bootstrapped |`.
- Create the vault note from `09 - Templates/Project Template.md` (fill Problem/Goal from the pitch; add the repo path) and version it:
```bash
VAULT="$HOME/Data Engineering/Second Brain"
# write "$VAULT/07 - Laboratory/$NAME.md" with the Write tool, then:
git -C "$VAULT" add "07 - Laboratory/$NAME.md" && git -C "$VAULT" commit -m "docs: add $NAME project note" && git -C "$VAULT" push
```

## 5. Commit and PR
```bash
git add "projects/$NAME" README.md
git commit -m "feat($NAME): bootstrap project from template"
git push -u origin HEAD
gh pr create --base dev --title "feat($NAME): bootstrap project" --body "Closes #$ISSUE"
```
Do not merge — show Tomas the PR link and wait for his OK.

## 6. Next
The project's design starts with brainstorming; its spec and plans go to `projects/$NAME/docs/design/{specs,plans}/`. `docs/guide.md` is filled during the tutor reviews as the project is built.
