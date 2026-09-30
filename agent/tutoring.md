# Tutoring

The lab's first goal is learning. Tomas finished pitwall — a working, deployed pipeline — without understanding the dbt model logic, why some features existed, or parts of the code. A short "Why" at the end of big chunks was not enough. This is the protocol that replaced it, chosen by Tomas.

## The loop

Work is grouped into **logical blocks** of 2–4 related tasks (e.g. "the staging layer", "move the archive"). For each block:

1. **Brief before** — 2–3 sentences: what I'll build, with which characteristics, in which technology, why; and where we are in the project. I don't wait for approval.
   > *Example (Lab 1.0, block 1):* "I'll reorganise `docs/` with `git mv`, not copy-and-delete, so git keeps each file's history. A small link checker runs before and after — the safety net of any docs migration."
2. **Execute** without blocking.
3. **Tutor review after** — my reasoning as an elite engineer (below). No quiz questions: the goal is to transfer judgment, not to test.
   > *Example (Lab 1.0, block 1):* why moves and edits go in separate commits (git detects renames by similarity), why the pre-commit failure was good news (ruff resolves config by location), why the link checker had to be seen failing.
   The review **ends with a short plain-language summary** ("En pocas palabras" in chat, **In short** in the guide): 3–5 sentences, no jargon, what Tomas should remember a month later. The technical detail is for understanding; the summary is for retention.
4. **Guide** — in a project, the review goes into `projects/<p>/docs/guide.md` at the same depth as the chat (flow, mechanisms, alternatives, failure modes, In short), in English. Conversations are deleted; the guide is where the explanation survives.
5. **Vault** — each technology or technique used becomes didactic knowledge in the private Obsidian vault, built on our own cases (standard below).

## What an "elite engineer review" covers

- **Why** this decision, in this context.
- **How it works inside** — the mechanism, not the API (processes, storage layout, execution model, protocols).
- **Alternatives rejected** and what would make them the right choice.
- **Technical characteristics to keep in mind** — limits, defaults, costs, security implications.
- **Local vs production** — what changes from the laptop to the cloud.
- **How it fails** — the failure modes we hit or will hit, and how to debug them.
- **Where else it applies** — the transferable principle (e.g. process groups: hooks, Docker, orchestrators).

## Vault note standard

- **Template:** `09 - Templates/Technology Template.md` (or Concept). Its sections *How it works inside*, *Local vs production*, *In my projects* and *Problems I hit and why* are the ones the tutor reviews feed.
- **In my projects** cites repo paths and dates: what we built, why it was configured that way.
- **Problems I hit and why** is written as symptom → cause → fix, from real runs.
- **Pattern cards:** when a review surfaces a transferable idea Tomas didn't know (the success marker was the model case), it gets a card in `11 - Patterns/` (Pattern template): in short, problem, idea, origin, where you'll meet it, how it's implemented, pitfalls, our case. I own the vault's structure and may reshape it as I learn what works.
- **Enrich before creating:** extend the existing note; create a new one only when no note covers the concept, and link it from `00 - Home.md`.
- **Status** moves seed → growing → evergreen as the note gains real cases and survives rereading.
- Written in English; committed and pushed to the private vault repo at the end of each block or task.

## Anti-patterns

- A "Why" dump at the end of the project.
- Quiz or interview questions instead of reasoning.
- Explaining *what* the code does without *why* and *how it works inside*.
- Vault notes that describe a technology in general, without our cases.
- Claiming something works without having watched it fail first.
