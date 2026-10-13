---
name: new-project
description: Start a new data engineering project from this lab — checks the stack is industry-standard, creates the project's own repository from template/ (local clone next to the lab, public GitHub repository with dev/main, rulesets and labels), registers it in the lab README, hub and vault. Use when Tomas asks to start, create or bootstrap a project.
---

# New project

One repository per project (lab ADR 0007). The lab stays the base: this session runs in the lab, the project is a sibling clone in `~/Data Engineering/Proyectos Data/<name>`, added to the session as a working directory.

**Every bash block is self-contained and starts with an explicit `cd`:** shell variables do not survive between tool calls and the Bash tool resets its directory outside the session's folders. Set `NAME` again in each block.

## 1. Name (validate before touching GitHub)
Ask for (or confirm) a kebab-case name and a one-line pitch.
```bash
NAME=<name>
[[ "$NAME" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]] || { echo "invalid name: $NAME"; exit 1; }
PKG="${NAME//-/_}"
python3 -c "import keyword,sys; n=sys.argv[1]; sys.exit(keyword.iskeyword(n) or n in sys.stdlib_module_names)" "$PKG" \
  || { echo "$PKG clashes with a Python keyword or stdlib module"; exit 1; }
[[ -e "$HOME/Data Engineering/Proyectos Data/$NAME" ]] && { echo "folder already exists"; exit 1; }
gh repo view "TomasRipsky/$NAME" >/dev/null 2>&1 && { echo "repository already exists"; exit 1; }
echo "ok: $NAME"
```
Also reject names equal to a planned dependency (e.g. `pytest`, `pandas`) — ask Tomas for another.

## 1b. Industry-standard check
For the intended core stack (ingestion, storage, transformation, orchestration, serving), state the market signal of each choice in one line: job-market demand and adoption. Sources: vault `08 - Research/Market Signals 2026.md` and `lab/tech-radar.md`; check current signals (web) when a tech is not there. A niche choice needs an explicit reason Tomas accepts — it becomes an ADR in the project's `docs/decisions/`. If a tech enters Trial, update `lab/tech-radar.md` in the lab PR of step 4.

## 2. Local repository from the template
```bash
NAME=<name>; PKG="${NAME//-/_}"
LAB="$HOME/Data Engineering/Claude Code Enviroment"; DEST="$HOME/Data Engineering/Proyectos Data/$NAME"
git -C "$LAB" fetch -q origin dev
mkdir -p "$DEST" && git -C "$LAB" archive origin/dev template | tar -x -C "$DEST" --strip-components=1   # tracked files of dev only
cd "$DEST" && rm -f uv.lock
mv "src/template_project" "src/$PKG"
grep -rl -e template-project -e template_project -e '# Project Name' . \
  | xargs perl -pi -e "s/template-project/$NAME/g; s/template_project/$PKG/g; s/^# Project Name\$/# $NAME/; s/^# Project Name — /# $NAME — /"
```
Add the folder to the session (`request_directory` with `$DEST`), then fill the placeholders with the Edit tool (not sed — the pitch may contain `/`, `&` or `|`):
- `README.md`: the `> One-sentence pitch...` line → `> $PITCH`.
- `pyproject.toml`: `description = "..."` → the pitch.
- `src/$PKG/__init__.py`: docstring → `"""$NAME: <pitch>."""`.

```bash
cd "$HOME/Data Engineering/Proyectos Data/<name>" && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .
```
All must pass before continuing.

## 3. GitHub repository (public — get Tomas's OK first)
Creating a public repository is a public action: state the name and visibility and wait for his OK.
```bash
NAME=<name>; cd "$HOME/Data Engineering/Proyectos Data/$NAME"
git init -q -b main && git add -A
git commit -q -m "chore: bootstrap from the Data Engineering Lab template"   # the one commit made directly on main: there is no history to protect yet
git branch dev
gh repo create "TomasRipsky/$NAME" --public --disable-wiki --description "<pitch>" --source . --remote origin
git push -q -u origin main dev && git switch -q dev
gh api -X PATCH "repos/TomasRipsky/$NAME" -f default_branch=dev -F allow_rebase_merge=false -F delete_branch_on_merge=true -q .default_branch
# same branch protection and labels as the lab
for id in $(gh api repos/TomasRipsky/data-engineering-lab/rulesets -q '.[].id'); do
  gh api "repos/TomasRipsky/data-engineering-lab/rulesets/$id" -q '{name,target,enforcement,conditions,rules,bypass_actors}' \
    | gh api -X POST "repos/TomasRipsky/$NAME/rulesets" --input - -q '"ruleset \(.name): \(.enforcement)"'
done
gh label clone TomasRipsky/data-engineering-lab -R "TomasRipsky/$NAME" -f
gh label list -R "TomasRipsky/$NAME" --json name -q '.[].name' | grep -v '^type:' | while read -r l; do gh label delete "$l" -R "TomasRipsky/$NAME" --yes; done
pre-commit install
gh repo view "TomasRipsky/$NAME" --json url,defaultBranchRef,visibility
```
`ci` runs on every pull request from the first one. Cloud wiring (GitHub Environments, Workload Identity Federation bound to **this repository's numeric ID**, Pages with a workflow build) comes with the project's design, not here — pitwall's `infra/gcp/iam.tf` and `make gh-vars` are the reference.

## 4. Register in the lab (a lab PR, through `ship`)
From the lab checkout: issue `chore(lab): register <name>` → branch from `dev` →
- a row in the `## Projects` table of `README.md`, linking the repository URL (the `world-status` hook reads this table): `| [$NAME](https://github.com/TomasRipsky/$NAME) | $PITCH | TBD | 🌱 bootstrapped |` (escape `|` in the pitch as `\|`);
- a card in `site/index.html` once the project has a public site (not before);
- `lab/tech-radar.md` if step 1b moved a tech.

Then the vault note from `09 - Templates/Project Template.md` (Problem/Goal from the pitch; repository URL and local path):
```bash
NAME=<name>; VAULT="$HOME/Data Engineering/Second Brain"
# write "$VAULT/07 - Laboratory/$NAME.md" with the Write tool, then:
git -C "$VAULT" add "07 - Laboratory/$NAME.md" && git -C "$VAULT" commit -m "docs: add $NAME project note" && git -C "$VAULT" push
```

## 5. Next
The project's design starts with brainstorming; its spec and plans go to `docs/design/{specs,plans}/` **in the project repository**, its decisions to `docs/decisions/`. `docs/guide.md` is filled during the tutor reviews as the project is built. Every change there follows the same flow as here — issue → branch from `dev` → PR → `ship` run against that repository. When a project teaches something reusable, improve `template/` in the lab.
