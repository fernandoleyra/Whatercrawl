# API-Key Audit & Stale Reference Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all stale references to `ANTHROPIC_API_KEY`, Claude Vision, and CSS selector self-healing from config, docs, and source comments — the Anthropic SDK is not used anywhere in the codebase.

**Architecture:** Pure surgical edits — no new code, no new files. Every changed file already exists. The Watercrawl server runs entirely on Playwright + trafilatura + DuckDuckGo HTML + SQLite; no LLM API is needed at runtime.

**Tech Stack:** Python (src/), Markdown (docs + plugin skills), .env config

## Global Constraints

- Do not add the `anthropic` package back to requirements.txt
- Do not touch BRIEF.md — it is a historical requirements document, not live documentation
- Do not delete `src/healing/__init__.py` — the empty file is harmless and removing it requires a git rm; leave it
- All changes should be minimal — fix only the stale text, nothing else

---

### Findings Summary

| File | Issue |
|---|---|
| `.env.example` | `ANTHROPIC_API_KEY` line still present — key is not used in source |
| `README.md` line 5 | "via a vision-based fallback" — feature was removed |
| `watercrawl-plugin/skills/watercrawl-scrape/SKILL.md` line 46 | `markdown` output description says "vision fallback for JS-heavy pages" |
| `src/crawler/site_crawler.py` lines 107-108 | `take_screenshot` docstring says "required for vision fallback" |

---

### Task 1: Remove ANTHROPIC_API_KEY from .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Remove the API key line**

Remove lines 1-2 (`ANTHROPIC_API_KEY=your_anthropic_api_key_here` and the blank separator before `# Server`).

After edit, `.env.example` should start with:
```
# Server
HOST=0.0.0.0
PORT=8000
...
```

- [ ] **Step 2: Commit**
```bash
git add .env.example
git commit -m "chore: remove unused ANTHROPIC_API_KEY from .env.example"
```

---

### Task 2: Fix README.md tagline

**Files:**
- Modify: `README.md` line 5

- [ ] **Step 1: Remove "via a vision-based fallback"**

Old:
```
...with better extraction quality via a vision-based fallback and lower cost when self-hosted.
```
New:
```
...with better extraction quality and lower cost when self-hosted.
```

- [ ] **Step 2: Commit**
```bash
git add README.md
git commit -m "docs: remove vision-based fallback from tagline — feature was removed"
```

---

### Task 3: Fix watercrawl-scrape skill output format description

**Files:**
- Modify: `watercrawl-plugin/skills/watercrawl-scrape/SKILL.md` line 46

- [ ] **Step 1: Remove vision fallback note**

Old:
```
- `markdown` (default) — clean Markdown, vision fallback for JS-heavy pages
```
New:
```
- `markdown` (default) — clean Markdown via trafilatura
```

- [ ] **Step 2: Commit**
```bash
git add watercrawl-plugin/skills/watercrawl-scrape/SKILL.md
git commit -m "docs: remove stale vision fallback note from scrape skill"
```

---

### Task 4: Fix site_crawler.py docstring

**Files:**
- Modify: `src/crawler/site_crawler.py` lines 107-108

- [ ] **Step 1: Update the take_screenshot docstring**

Old:
```python
        take_screenshot: If True, each page screenshot is captured (required for
            vision fallback in crawl jobs that produce markdown output).
```
New:
```python
        take_screenshot: If True, each page screenshot is captured and stored with the result.
```

- [ ] **Step 2: Commit**
```bash
git add src/crawler/site_crawler.py
git commit -m "docs: remove stale vision fallback reference from site_crawler docstring"
```

---

### Task 5: Push

- [ ] **Step 1: Push all commits**
```bash
git push origin main
```
