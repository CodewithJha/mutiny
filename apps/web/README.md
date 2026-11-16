# Mutiny Hosted UI

Next.js frontend for Mutiny's Hosted lineage API. Customer campaigns execute
locally through `mutiny run`; `mutiny run --hosted` sends redacted results to
Hosted for viewing projects, campaigns, candidates, and regressions.

## Local development

Requires Python >= 3.11, uv, and Node.js >= 20 with npm. From the repository root:

```bash
uv sync --group dev
cd apps/web
npm ci
cd ../..
```

Start the API in one terminal, from the repository root:

```bash
uv run python -m mutiny_api --host 127.0.0.1 --port 8000
```

Start the UI in another terminal, from `apps/web`:

```bash
npm run dev
```

On Windows PowerShell, use this alternative to the npm script's POSIX environment
assignment:

```powershell
$env:WATCHPACK_POLLING = 'true'
npx next dev --hostname 127.0.0.1 --port 3000
```

Open <http://127.0.0.1:3000>. Check API health at
<http://127.0.0.1:8000/api/health>. With dependencies installed, POSIX shells can
also start both processes using `./scripts/dev.sh` from the repository root.

## API connection

`next.config.ts` forwards `/api/*` to `MUTINY_API_URL`, defaulting to
`http://127.0.0.1:8000`. Set it on the web process before starting Next.js if the
API runs elsewhere. When the API uses `MUTINY_API_TOKEN`, set the same token on
the web process; middleware adds the bearer header for API requests. Keep this
token server-side. Non-loopback API binds require a token.

The middleware does not authenticate browser visitors: access to this UI is
equivalent to possession of the operator token. Keep it on a trusted local
machine. Before exposing it to a LAN or public network, add a separate
authenticated proxy covering pages and `/api/*`, including SSE. Compose binds
both host ports to loopback by default. Setting the API token alone does not
protect an exposed UI; see [SECURITY.md](../../SECURITY.md#hosted-authentication-m-pr7--p0-1--p0-4).

The Hosted API is **unreleased**. Its internal `mutiny-api` metadata version is
independent of the published CLI/Core version. Source checkout or workspace
installation supplies the API; `pip install mutiny-ai` supplies the customer CLI.

## Checks

From `apps/web`:

```bash
npm run lint
npm test
npx tsc --noEmit
npm run build
```

`npm test` uses Node's built-in test runner and the existing TypeScript compiler
to render the Policies page without API access and check that retired policy
file operations are absent from the Hosted client.

See [CONTRIBUTING.md](../../CONTRIBUTING.md),
[Cold start](../../docs/COLD_START.md), and [SECURITY.md](../../SECURITY.md)
for the full contributor workflow and Hosted operating requirements.
