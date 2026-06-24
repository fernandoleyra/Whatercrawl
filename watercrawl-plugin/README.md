# Watercrawl Claude Code Plugin

Gives Claude Code three scraping commands powered by your local Watercrawl service.

## Requirements

1. Clone and start Watercrawl:
   ```bash
   git clone https://github.com/YOUR_USERNAME/watercrawl
   cd watercrawl
   cp .env.example .env  # add ANTHROPIC_API_KEY
   docker-compose up
   ```

2. Install this plugin:
   ```bash
   claude plugins install watercrawl
   ```

## Commands

| Command | What it does |
|---------|-------------|
| `/watercrawl-scrape` | Scrape one URL → Markdown |
| `/watercrawl-crawl` | Crawl entire site → all pages as Markdown |
| `/watercrawl-extract` | Scrape URL → structured JSON matching your schema |

## Configuration

Set `WATERCRAWL_URL` in your shell to point at a non-localhost instance:

```bash
export WATERCRAWL_URL=https://api.watercrawl.io
```

## Skills

The plugin also registers three skills that activate automatically when you describe
scraping tasks in natural language — no slash command needed.
