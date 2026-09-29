---
name: new-project
description: Start a new data engineering project in this lab — creates the GitHub issue, branch from dev, copies projects/_template, renames the package, registers it in the README and opens a PR. Use when Tomas asks to start, create or bootstrap a project.
---

# New project

## 1. Name
Ask for (or confirm) a kebab-case name and a one-line pitch.
Validate: `[[ "$NAME" =~ ^[a-z][a-z0-9-]*$ ]]` — reject otherwise (no leading digit, no underscores, no uppercase).
Derive `PKG="${NAME//-/_}"`. Stop if `projects/$NAME` already exists.

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
  | xargs sed -i '' -e "s/template-project/$NAME/g" -e "s/template_project/$PKG/g" -e "s/^# Project Name$/# $NAME/"
(cd "projects/$NAME" && uv sync && uv run pytest && uv run ruff check .)
```
All three must pass before continuing.

## 4. Register
- Append a row to the `## Projects` table in the root `README.md`: `| [$NAME](projects/$NAME/) | $PITCH | TBD | 🌱 bootstrapped |`.
- Create `~/Data Engineering/Second Brain/07 - Laboratory/$NAME.md` from `09 - Templates/Project Template.md` (fill Problem/Goal from the pitch; add the repo path).

## 5. Commit and PR
```bash
git add "projects/$NAME" README.md
git commit -m "feat($NAME): bootstrap project from template"
git push -u origin HEAD
gh pr create --base dev --title "feat($NAME): bootstrap project" --body "Closes #$ISSUE"
```
Do not merge — show Tomas the PR link and wait for his OK.
