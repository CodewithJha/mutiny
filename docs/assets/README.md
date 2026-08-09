# Docs assets

Screenshots and short demo recordings for the root README live here.

## Checked-in captures (PNG / GIF)

Real Hosted UI captures from [mutiny-sable.vercel.app](https://mutiny-sable.vercel.app) plus a local CLI frame. SVG storyboard remains as a static diagram fallback.

| File | Content |
|---|---|
| `hero.png` | Hosted landing / first viewport |
| `campaign.png` | Hosted `/campaigns` (list + violation statuses) |
| `regressions.png` | Hosted `/campaign/{id}` violation + evolution graph + tool evidence |
| `policy.png` | Hosted `/policies` |
| `tests.png` | Hosted `/tests` |
| `cli-run.png` | Terminal: `mutiny run --no-hosted` finding a violation |
| `mutiny-demo.gif` | Short slideshow of the frames above |
| `storyboard.svg` | Loop diagram (static fallback) |
| `*.svg` (other) | Legacy mocks kept for reference; README prefers PNG/GIF |

## Refreshing captures

1. Hosted stills (prefer waiting for network idle):

   ```bash
   # example: puppeteer-core + Chrome headless against the live URL
   # or local ./scripts/dev.sh then screenshot http://127.0.0.1:3000
   ```

2. CLI frame:

   ```bash
   cd examples/openai_support_agent
   mutiny run --no-hosted
   # capture terminal; scrub personal absolute paths before committing
   ```

3. Rebuild GIF from PNGs with ffmpeg (keep under ~500 KB if possible).

4. Keep README **Screenshots & demo** paths pointing at the PNG/GIF basenames above.

## Guidelines

- Still frames: PNG or WebP, prefer &lt; ~1 MB each.
- Scrub API keys and personal home-directory paths.
- Alt text in README should describe the real UI.
