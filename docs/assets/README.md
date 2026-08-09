# Docs assets

Screenshots and short demo recordings for the root README live here.

## Checked-in placeholders (SVG)

Intentional UI/terminal mock frames — **not** broken image links. Replace with real captures when you have them (keep the same basename, prefer `.png` / `.webp` / `.gif`, then update README image paths).

| File | Intended real shot |
|---|---|
| `hero.svg` → `hero.png` | Hosted landing / first viewport |
| `campaign.svg` → `campaign.png` | Hosted campaign / lineage |
| `policy.svg` → `policy.png` | `policy.yaml` or Hosted `/policies` |
| `tests.svg` → `tests.png` | Hosted `/tests` or `mutiny test` output |
| `regressions.svg` → `regressions.png` | `.mutiny/tests/` artifact view |
| `cli-run.svg` → `cli-run.png` | Terminal: `uv run mutiny run --no-hosted` |
| `storyboard.svg` | Loop diagram (keep until a GIF exists) |
| `hosted-campaign.svg` / `policy-yaml.svg` | Aliases of campaign / policy placeholders |

## Dropping a real GIF later

1. Record the sample loop (asciinema, terminal.sexy, or screen capture):

   ```bash
   cd examples/openai_support_agent
   uv run mutiny init
   uv run mutiny run --no-hosted
   uv run mutiny test
   ```

2. Export as `docs/assets/mutiny-demo.gif` (or `.webm`), keep under ~2 MB if possible.
3. In the root README **Screenshots & demo** section, put the GIF **above** the storyboard SVG and keep the SVG as a static fallback.
4. Open a PR with label `docs` / `examples`.

## Guidelines

- Still frames: PNG or WebP, &lt; ~1–2 MB each.
- Prefer dark terminal / Hosted UI captures that match the product voice.
- Alt text in README should describe the real UI once placeholders are replaced.
