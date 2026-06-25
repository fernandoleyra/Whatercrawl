# Publishing Watercrawl to the Claude Code Marketplace

## What to upload

| File / Directory | Purpose |
|---|---|
| `skills/` | Nine skill files |
| `commands/` | Ten command files |
| `assets/` | Icon and banner images |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Registry entry |
| `README.md` | User-facing documentation |
| `CHANGELOG.md` | Version history |
| `LICENSE` | MIT license |

## Marketplace submission steps

1. Push the `watercrawl-plugin/` directory as a standalone GitHub repo: `github.com/fernandoleyra/watercrawl`
2. Tag the release:
   ```bash
   git tag v1.0.0
   git push origin main --tags
   ```
3. Create a GitHub Release with CHANGELOG content as release notes
4. Submit to the Claude Code plugin registry:
   - Plugin name: `watercrawl`
   - Owner: `fernandoleyra`
   - Source: `https://github.com/fernandoleyra/watercrawl`

## Install command (for users)

```
/plugin marketplace add fernandoleyra/watercrawl
/plugin install watercrawl
```
