# Deploy backend to ECS Express Mode: task board

This file covers moving the FastAPI backend to AWS ECS Express Mode (us-west-2) and connecting it to the
Expo web app on Amplify. It is laid out for pasting into Trello. Every agent card is written to be used as
a Claude Code prompt on its own.

## How to load this into Trello

1. **Cards:** for each epic below, copy the "Card titles" block. In Trello, click **Add a card** in your To Do
   list and paste. Trello offers to create one card per line, so pick **Create N cards**.
2. **Descriptions:** open a card and paste its "Description" block into the description field.
   Trello renders it as markdown.
3. **Checklists:** add a checklist to the card and paste its "Checklist" block. Trello creates one item per line.
4. **Labels:** create these once. Owner labels: `Agent`, `You`. Epic labels: `Prep`, `Backend`,
   `Front end`, `AWS setup`, `CI/CD`, `Launch`, `Docs`.

The code-block copy button on GitHub works well for steps 1–3.

### Dependency overview

| Card                                  | Depends on                              |
| ------------------------------------- | --------------------------------------- |
| P1–P4, B1, B2, B5, F1, A0, A4, A5, A6 | nothing, can start now                  |
| B3, then B4                           | B2, in order (same file)                |
| F2                                    | F1 (same session)                       |
| A1, A2                                | A0 (runbook)                            |
| A3                                    | A0, A1 (bucket name)                    |
| C1                                    | B1                                      |
| C2                                    | A0, A2, A3                              |
| D1                                    | B1–B5 merged (F1–F2 for front-end vars) |
| L1                                    | B1–B5, C1, C2, P1                       |
| L2                                    | L1, A1, A3, A4                          |
| L3                                    | L2                                      |
| L4                                    | L2, F1–F2, A6                           |
| L5                                    | L4                                      |
| L6                                    | L5                                      |

**Critical path:** B1 → C1 → (A2, A3 → C2) → L1 → L2 → L4 → L5.

---

## Shared context (agents: read this first)

**Why:** the Expo web app is live on Amplify, but scanning fails. The web client calls `http://<hostname>:8000`,
which doesn't exist on Amplify, and an HTTPS page can't call an `http://` backend. The backend moves to
**ECS Express Mode** in **us-west-2**, which runs a container image from ECR behind a managed HTTPS load balancer.

**Rules for every agent card**

- Work on a branch named `deploy/<card-id>-<short-slug>` (e.g. `deploy/b2-threadpool-scan`) and open a PR to `master`.
  Never push to `master` directly: it auto-deploys the front end, and later the backend too.
- **Local dev must keep working unchanged.** With none of the new env vars set, the backend and app behave exactly as today.
- Follow `CLAUDE.md`. The pre-commit hook runs `pytest` (from `backend/`). Keep the suite green and add tests for new behavior.
- The repo is **public**. Never commit secrets, the Order Guide PDF, or barcode images.

**Backend env var contract** (names are fixed, so cards stay compatible)

| Var                     | Default (unset)                         | Meaning                                                    |
| ----------------------- | --------------------------------------- | ---------------------------------------------------------- |
| `AWS_REGION`            | `us-east-1` in code; set `us-west-2`    | Region for Rekognition and S3                              |
| `IMAGES_BUCKET`         | unset → local disk                      | S3 bucket for `crops/` and `barcodes/`                     |
| `PRESIGNED_URL_TTL`     | `3600`                                  | Seconds a presigned GET URL is valid                       |
| `ENABLE_DEBUG_IMAGES`   | `true`                                  | Write the annotated debug image; `false` in prod           |
| `API_KEY`               | unset → auth disabled (warn at startup) | Required value of the `X-API-Key` header on `/api/v1/scan` |
| `ALLOWED_ORIGINS`       | `*`                                     | Comma-separated CORS origins; prod = the Amplify URL       |
| `REKOGNITION_LOG_LEVEL` | `INFO`                                  | Existing                                                   |

**Front-end env vars** (Expo inlines `EXPO_PUBLIC_*` at build time)

| Var                       | Used by      | Meaning                                                    |
| ------------------------- | ------------ | ---------------------------------------------------------- |
| `EXPO_PUBLIC_WEB_API_URL` | web only     | Backend base URL. Unset → today's `http://<hostname>:8000` |
| `EXPO_PUBLIC_API_URL`     | native only  | Existing (LAN IP in `mobile/.env`). Unchanged              |
| `EXPO_PUBLIC_API_KEY`     | web + native | Sent as `X-API-Key` when set                               |

**Fixed names**

| Thing                 | Value                                                                    |
| --------------------- | ------------------------------------------------------------------------ |
| S3 key layout         | `crops/<filename>.jpg`, `barcodes/<cic>.png`                             |
| Health check          | `GET /health` → `200 {"status": "ok"}`, no auth                          |
| ECR repository        | `theia-backend`                                                          |
| Container port        | `8000`                                                                   |
| IAM roles             | `theia-task-role`, `theia-execution-role`, `theia-github-deploy-role`    |
| GitHub repo variables | `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `ECR_REPOSITORY`, `ECS_SERVICE_ARN` |

**Unverified Express Mode details:** the health-check, port, env-var and min-task fields, and the exact CLI
command to update a service's image, still need checking (card P2). If you need one and P2's notes
(`docs/deploy/EXPRESS_MODE_NOTES.md`) don't exist, check AWS docs or the CLI help. Do not guess. Leave a clearly
marked TODO that fails loudly.

---

## Epic: Prep

### Card titles

```text
P1 · Commit or discard pending products.json edits
P2 · Confirm Express Mode in us-west-2 and record its settings
P3 · Switch local backend .env to us-west-2
P4 · Enable the Trello GitHub Power-Up
```

### P1 · Commit or discard pending products.json edits

Labels: `You`, `Prep` · Depends on: none

Description

```text
The backend pipeline builds from git only, so uncommitted catalog edits never reach the deployed service. `backend/products.json` has uncommitted changes.

Done when: `git status` shows `backend/products.json` clean, either committed or discarded.
```

Checklist

```text
Review the diff of backend/products.json
Commit it (or discard)
```

### P2 · Confirm Express Mode in us-west-2 and record its settings

Labels: `You`, `Prep` · Depends on: none

Description

```text
Several later cards depend on Express Mode details that are not verified yet. Open ECS in the AWS console with the region set to us-west-2 (Oregon), start "Create" for an Express Mode service, and write down what the form offers. Don't create anything yet.

Record the answers in docs/deploy/EXPRESS_MODE_NOTES.md (commit it). Cards A0, C1 and L2 read it.

Done when: the notes file answers every checklist item.
```

Checklist

```text
Express Mode is available in us-west-2
Container port field (can it be 8000?)
Health check path field (can it be /health?) and its default
CPU/memory options (is 1 vCPU / 2 GB offered? 0.5 vCPU / 1 GB?)
Environment variables field (plain env vars supported?)
Which IAM roles it asks for (task role, execution role, infrastructure role) and whether it offers to create any
Autoscaling min/max fields (is min 0 allowed?)
What the service URL looks like (HTTPS, domain format)
The AWS CLI command to update the service's image (check the docs; expected something like aws ecs update-express-gateway-service)
```

### P3 · Switch local backend .env to us-west-2

Labels: `You`, `Prep` · Depends on: none

Description

```text
Keep local dev in the same region as production. Rekognition holds no data, so nothing needs migrating. Your existing IAM user's keys work in any region.

Done when: backend/.env has AWS_REGION=us-west-2 and a local scan still works.
```

Checklist

```text
Set AWS_REGION=us-west-2 in backend/.env
Restart the backend and run one scan
```

### P4 · Enable the Trello GitHub Power-Up

Labels: `You`, `Prep` · Depends on: none

Description

```text
Link agent PRs to their cards so each card shows PR status (open/merged).

1. Board → Power-Ups → Add Power-Ups → search "GitHub" → Add the official one.
2. Power-Up settings (gear) → Authorize account → sign in to GitHub → Authorize Trello.
3. On a card: GitHub (in the card's Power-Ups section) → Attach Pull Request → SanAdams/project-theia → pick the PR. Pasting a PR URL as an attachment also works.

Trello's menu labels may differ slightly from these.

Done when: one test card shows an attached PR or branch.
```

Checklist

```text
Add the GitHub Power-Up
Authorize your GitHub account
Attach a PR or branch to a test card
```

---

## Epic: Backend

### Card titles

```text
B1 · Containerize the backend (Dockerfile, .dockerignore, /health)
B2 · Move scan work off the event loop
B3 · Add S3 storage for crops and barcodes
B4 · Gate debug images behind ENABLE_DEBUG_IMAGES
B5 · Require an API key on /scan and make CORS origins configurable
```

### B1 · Containerize the backend (Dockerfile, .dockerignore, /health)

Labels: `Agent`, `Backend` · Depends on: none

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: ECS Express Mode runs a container image, so the backend needs a Dockerfile. GitHub Actions builds it with backend/ as the build context. The load balancer needs a health endpoint.

Do:
- backend/Dockerfile: python:3.12-slim. Install requirements.txt with --no-cache-dir. Copy the app. Create the static/ directory: main.py mounts StaticFiles(directory="static"), which raises at startup if it's missing. Run as a non-root user. EXPOSE 8000. CMD uvicorn main:app --host 0.0.0.0 --port 8000.
- backend/.dockerignore: venv/, .env, __pycache__/, tests/, eval/, scripts/, static/*, "Order Guide.pdf", .pytest_cache/. products.json MUST be included.
- GET /health in main.py returning {"status": "ok"}, with no auth and outside the /api/v1 router.

Files: backend/Dockerfile (new), backend/.dockerignore (new), backend/main.py, backend/tests/ (new test for /health)

Done when:
- pytest passes, including a /health test.
- If Docker is available: docker build -t theia-backend backend/ succeeds, and docker run -p 8000:8000 theia-backend serves /health with 200. If Docker isn't available, say so in the PR and C1's CI build will be the first real build.
- The image contains no .env, PDF, or barcode images.
```

Checklist

```text
Dockerfile (python:3.12-slim, non-root, static/ created, port 8000)
.dockerignore
GET /health + test
Build and run locally if Docker is available
PR opened and linked to this card
```

### B2 · Move scan work off the event loop

Labels: `Agent`, `Backend` · Depends on: none (B3 and B4 come after; same file)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: scan_image in backend/app/routers/inventory.py is `async def`, but it calls Rekognition synchronously (DetectLabels, then DetectText once per box region in app/services/rekognition.py). While a scan runs, the event loop is blocked, so the server can't answer /health. Behind a load balancer, failed health checks can get the task killed mid-scan.

Do: make the scan endpoint not block the loop. Preferred: change it to a plain `def` (FastAPI runs sync endpoints in a threadpool) and read the upload with `file.file.read()`. Alternative: keep async and wrap the blocking work in `run_in_threadpool`. Keep the response shape identical.

Files: backend/app/routers/inventory.py, backend/tests/test_inventory_router.py

Done when:
- All existing router tests pass unchanged.
- New test: with detect_box_labels faked to sleep (e.g. 1 s), a concurrent GET /health returns before the scan finishes. Use httpx.AsyncClient with ASGITransport and asyncio.gather. httpx is already in requirements-dev.txt. The test should mount both the router and a /health route, or use main.app.
```

Checklist

```text
Make scan endpoint non-blocking
Concurrency test (/health answers during a slow scan)
Existing tests unchanged and green
PR opened and linked to this card
```

### B3 · Add S3 storage for crops and barcodes

Labels: `Agent`, `Backend` · Depends on: B2 (same file)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: crops are written to static/crops on local disk and barcodes are read from static/barcodes. A container's disk is wiped on restart and isn't shared between tasks. Barcodes are vendor material and must not be public, so in production both live in a private S3 bucket and the API returns presigned GET URLs. Local dev (no IMAGES_BUCKET) must behave exactly as today, including the crop prune.

Do: add backend/app/services/storage.py and route inventory.py's crop writes and barcode lookups through it.
- save_crop(filename, data) -> url
  - S3 mode: put_object to crops/<filename> (ContentType image/jpeg) and return a presigned GET URL (ExpiresIn = PRESIGNED_URL_TTL, default 3600). No prune: a bucket lifecycle rule expires crops/ after 1 day.
  - Local mode: today's behavior (write to CROPS_DIR, return /static/crops/<filename>, prune to MAX_CROP_IMAGES so this request never evicts its own new crops).
- barcode_url(cic) -> Optional[str]
  - S3 mode: list the barcodes/ prefix (paginate) and cache the set of CIC codes for ~5 minutes. If the CIC is present, return a presigned GET for barcodes/<cic>.png, else None.
  - Local mode: today's check of BARCODES_DIR/<cic>.png and return /static/barcodes/<cic>.png.
- S3 client: boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})). Regional SigV4 avoids signature/redirect errors on non-us-east-1 buckets. Create it lazily, like _get_client in rekognition.py.
- Failure handling: an S3 error on a barcode lookup or crop upload must not fail the scan. Log a warning and omit that URL.
- Note: presigned URLs stop working when the task-role credentials that signed them expire, which can be sooner than the TTL. That's acceptable; mention it in a code comment.

Files: backend/app/services/storage.py (new), backend/app/routers/inventory.py, backend/tests/ (storage tests; update the router fixture if constants move)

Done when:
- Existing router tests pass. Updating the fixture to patch the new location of CROPS_DIR/BARCODES_DIR/MAX_CROP_IMAGES is fine. Don't weaken assertions.
- New tests with a fake S3 client cover: crop put + presigned URL returned; barcode URL only for CICs present under barcodes/; barcode set cached (second call makes no list request); an S3 exception doesn't fail the scan.
- With IMAGES_BUCKET unset, a real local scan behaves as before.
```

Checklist

```text
storage.py with local + S3 modes
inventory.py uses save_crop / barcode_url
Barcode key set cached ~5 min
S3 errors logged, never fail the scan
Tests with fake S3 client
Existing tests green
PR opened and linked to this card
```

### B4 · Gate debug images behind ENABLE_DEBUG_IMAGES

Labels: `Agent`, `Backend` · Depends on: B3 (same file)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: each scan writes an annotated debug image to static/debug (pruned to 10). It's a developer aid. In production it's disabled to avoid useless writes. The front end never reads debug_image_url, so no UI change is needed.

Do: in inventory.py, run the debug-image block only when ENABLE_DEBUG_IMAGES is true (default true; accept true/false/1/0, case-insensitive). When disabled, debug_image_url is null.

Files: backend/app/routers/inventory.py, backend/tests/test_inventory_router.py

Done when: existing debug tests pass with the default, and a new test shows ENABLE_DEBUG_IMAGES=false yields debug_image_url null and writes no file.
```

Checklist

```text
Env flag gates the debug block (default true)
Test for disabled mode
PR opened and linked to this card
```

### B5 · Require an API key on /scan and make CORS origins configurable

Labels: `Agent`, `Backend` · Depends on: none

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: /api/v1/scan is unauthenticated and every call costs Rekognition money. The site will sit behind Amplify's password, and the web app sends a shared key in X-API-Key. CORS is currently allow_origins=["*"] in main.py.

Do:
- A FastAPI dependency (e.g. backend/app/auth.py, require_api_key) that compares the X-API-Key header to API_KEY with hmac.compare_digest and raises 401 on mismatch or absence. Read API_KEY at request time so tests can set it. If API_KEY is unset, allow everything and log a warning once at startup (lifespan).
- Apply it to the inventory router in main.py: include_router(..., dependencies=[Depends(require_api_key)]). /health and /static stay open.
- CORS: build allow_origins from ALLOWED_ORIGINS (comma-separated, trimmed; default "*"). Keep allow_headers broad enough to include x-api-key.

Files: backend/app/auth.py (new), backend/main.py, backend/tests/ (new auth/CORS tests)

Done when tests exercise the same wiring main.py uses (e.g. reload main after setting env, or factor a small helper both main.py and the test use) and show:
- API_KEY set: scan without header → 401; wrong key → 401; correct key → 200 (Rekognition faked as in test_inventory_router.py).
- API_KEY unset: scan works without a header.
- CORS preflight: OPTIONS /api/v1/scan with Origin = an allowed origin, Access-Control-Request-Method: POST, Access-Control-Request-Headers: x-api-key → 200 with access-control-allow-origin set, and no API key needed.
- A disallowed origin gets no access-control-allow-origin header.
```

Checklist

```text
require_api_key dependency (compare_digest, 401, disabled when unset)
Applied to the scan router only
ALLOWED_ORIGINS parsing
Tests: 401 / 200 / unset / preflight / disallowed origin
PR opened and linked to this card
```

---

## Epic: Front end

### Card titles

```text
F1 · Read backend URL and API key from env on web
F2 · Handle absolute image URLs in the results screens
```

### F1 · Read backend URL and API key from env on web

Labels: `Agent`, `Front end` · Depends on: none (do F1 then F2 in one session)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: mobile/src/services/api.ts hardcodes the web backend as http://${window.location.hostname}:8000. On Amplify, the backend lives at a separate HTTPS URL. EXPO_PUBLIC_API_URL is already used by the native path with a LAN IP from mobile/.env, so the web path gets its own variable. That way local web dev doesn't change.

Do:
- WEB_API_BASE_URL = process.env.EXPO_PUBLIC_WEB_API_URL, falling back to today's http://${window.location.hostname}:8000. Strip a trailing slash.
- If process.env.EXPO_PUBLIC_API_KEY is set, send it as the X-API-Key header on the web fetch call and on the native axios client. Keep the web path omitting Content-Type so the browser sets the multipart boundary.
- Leave the native base URL logic unchanged.

Files: mobile/src/services/api.ts

Done when: npx tsc --noEmit and npm run build (from mobile/) pass; with neither var set, a local web scan works exactly as today.
```

Checklist

```text
EXPO_PUBLIC_WEB_API_URL with hostname:8000 fallback
X-API-Key header on web + native when set
tsc + npm run build pass
Local web scan still works
PR opened and linked to this card
```

### F2 · Handle absolute image URLs in the results screens

Labels: `Agent`, `Front end` · Depends on: F1 (same session)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Context: in production, crop and barcode URLs become absolute presigned S3 URLs (https://...). Two call sites prefix resolvedApiBaseUrl onto every URL, which would produce broken links:
- mobile/src/components/CropGalleryModal.tsx (Image source uri)
- mobile/src/screens/ResultsScreen.tsx (barcode Image source uri)

Do: export resolveAssetUrl(url) from mobile/src/services/api.ts. Absolute http(s) URLs pass through unchanged; relative ones get resolvedApiBaseUrl prefixed. Use it at both call sites.

Files: mobile/src/services/api.ts, mobile/src/components/CropGalleryModal.tsx, mobile/src/screens/ResultsScreen.tsx

Done when: tsc and npm run build pass, and a local scan (relative /static URLs) still shows barcodes and the crop gallery on web.
```

Checklist

```text
resolveAssetUrl helper
Used in CropGalleryModal and ResultsScreen
tsc + npm run build pass
Local scan shows barcodes and crops
PR opened and linked to this card
```

---

## Epic: AWS setup (all in us-west-2)

### Card titles

```text
A0 · Write the AWS console runbook and IAM policy files
A1 · Create the S3 bucket and upload barcodes
A2 · Create the ECR repository
A3 · Create the IAM roles
A4 · Generate the API key
A5 · Set up an AWS Budgets alarm
A6 · Password-protect the Amplify site
```

### A0 · Write the AWS console runbook and IAM policy files

Labels: `Agent`, `AWS setup` · Depends on: P2 notes (helpful, not blocking; draft and mark unknowns)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first, and docs/deploy/EXPRESS_MODE_NOTES.md if it exists.

Context: the user sets up AWS through the console (us-west-2) and wants click-by-click steps with copy-paste policy JSON, using placeholders <ACCOUNT_ID>, <BUCKET>, <AMPLIFY_URL>.

Do:
- docs/deploy/RUNBOOK.md: console steps for cards A1, A2, A3, C2, L2, L3 and L4, in that order, with what to record after each step (ARNs, URLs).
- infrastructure/policies/:
  - task-role.json: rekognition:DetectLabels and rekognition:DetectText on "*"; s3:PutObject and s3:GetObject on arn:aws:s3:::<BUCKET>/crops/*; s3:GetObject on arn:aws:s3:::<BUCKET>/barcodes/*; s3:ListBucket on arn:aws:s3:::<BUCKET> with Condition s3:prefix "barcodes/*" (and "barcodes/").
  - task-role-trust.json: ecs-tasks.amazonaws.com.
  - github-deploy-trust.json: OIDC provider token.actions.githubusercontent.com, aud sts.amazonaws.com, sub exactly repo:SanAdams/project-theia:ref:refs/heads/master.
  - github-deploy-role.json: ecr:GetAuthorizationToken on "*"; push actions (BatchCheckLayerAvailability, InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage, BatchGetImage) on the theia-backend repo ARN; the ECS action(s) needed to update the Express Mode service (from P2 notes, else mark TODO); iam:PassRole on theia-task-role and theia-execution-role with Condition iam:PassedToService = ecs-tasks.amazonaws.com.
  - s3-lifecycle.json: expire objects under crops/ after 1 day.
  - ecr-lifecycle.json: keep the last 10 images.
- Mark anything that depends on unverified Express Mode details as "VERIFY IN CONSOLE".

Files: docs/deploy/RUNBOOK.md (new), infrastructure/policies/*.json (new)

Done when: every JSON file is valid JSON, least-privilege, and uses placeholders only, with no real account IDs. The runbook covers every listed card.
```

Checklist

```text
RUNBOOK.md covering A1, A2, A3, C2, L2, L3, L4
task-role.json + trust
github-deploy-role.json + trust (master branch only)
s3-lifecycle.json, ecr-lifecycle.json
Unverified items marked VERIFY IN CONSOLE
PR opened and linked to this card
```

### A1 · Create the S3 bucket and upload barcodes

Labels: `You`, `AWS setup` · Depends on: A0 (runbook)

Description

```text
A private bucket holds crops (expire after 1 day) and barcodes (kept). Follow docs/deploy/RUNBOOK.md.

Done when: the bucket exists in us-west-2 with all public access blocked, the lifecycle rule targets the crops/ prefix only, and barcodes/<cic>.png objects exist (about 530 files from backend/static/barcodes).
```

Checklist

```text
Create bucket in us-west-2 (name like theia-images-<something unique>), Block all public access ON
Lifecycle rule: prefix crops/, expire current versions after 1 day
Create folder barcodes/ and upload every PNG from backend/static/barcodes
Spot-check one key: barcodes/94981327.png
Record the bucket name (needed for A3 and L2)
```

### A2 · Create the ECR repository

Labels: `You`, `AWS setup` · Depends on: A0 (runbook)

Description

```text
The private registry the pipeline pushes images to. Follow docs/deploy/RUNBOOK.md.

Done when: a private repository named theia-backend exists in us-west-2 with a lifecycle policy that keeps the last 10 images.
```

Checklist

```text
Create private repo theia-backend (us-west-2)
Add lifecycle policy: keep last 10 images
Record the repository URI
```

### A3 · Create the IAM roles

Labels: `You`, `AWS setup` · Depends on: A0 (policy files), A1 (bucket name)

Description

```text
The roles the service runs with. Follow docs/deploy/RUNBOOK.md and infrastructure/policies/.

Done when these exist:
- theia-task-role: what the app itself may do (Rekognition x2, crops read/write, barcodes read/list)
- theia-execution-role: lets ECS pull the image and write logs (AWS managed policy AmazonECSTaskExecutionRolePolicy only)
- the infrastructure role Express Mode asks for (the console may offer to create it; see P2 notes)
```

Checklist

```text
theia-task-role with task-role.json (bucket name filled in)
theia-execution-role with AmazonECSTaskExecutionRolePolicy
Express Mode infrastructure role
Record all three role ARNs
```

### A4 · Generate the API key

Labels: `You`, `AWS setup` · Depends on: none

Description

```text
A shared secret the web app sends in X-API-Key. It ships inside the site's JS bundle, which is why the site itself goes behind a password (A6). Store it in your password manager; it gets pasted into the ECS service (L2) and Amplify (L4).

Done when: you have a random key of at least 32 characters saved in your password manager.
```

Checklist

```text
Generate a 32+ character random key (e.g. your password manager's generator)
Save it in your password manager
```

### A5 · Set up an AWS Budgets alarm

Labels: `You`, `AWS setup` · Depends on: none

Description

```text
An email warning if spend climbs. Expected running cost is roughly $40–60/month at 1 vCPU / 2 GB (an estimate; verify with the AWS Pricing Calculator), plus small per-use Rekognition and S3 charges.

Billing and Cost Management → Budgets → Create budget → Cost budget, monthly.

Done when: a monthly budget exists with email alerts.
```

Checklist

```text
Pick a monthly amount a bit above the expected cost (e.g. $75)
Alert at 80% of actual spend
Alert at 100% of forecasted spend
Confirm the alert email address
```

### A6 · Password-protect the Amplify site

Labels: `You`, `AWS setup` · Depends on: none. Must be done **before L4**.

Description

```text
Users are known staff, so the whole site, including the JS bundle that will contain the API key, goes behind one shared username and password. No code.

Amplify console → your app → Access control (under App settings or Hosting) → Manage access → branch master → Restricted (password required) → set a username and password → Save.

Done when: opening the Amplify URL in a private window prompts for credentials, and the credentials have been shared with staff.
```

Checklist

```text
Enable access control on master
Verify the prompt in a private window
Share the credentials with staff
```

---

## Epic: CI/CD

### Card titles

```text
C1 · Add the GitHub Actions backend workflow
C2 · Connect GitHub to AWS (OIDC role and repo variables)
```

### C1 · Add the GitHub Actions backend workflow

Labels: `Agent`, `CI/CD` · Depends on: B1

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first, and docs/deploy/EXPRESS_MODE_NOTES.md if it exists.

Context: Express Mode deploys from ECR and can't build from GitHub, so a workflow builds and pushes the image and then updates the service. The repo is public. Use OIDC (no stored AWS keys), keep configuration in repo variables, and never expose AWS credentials to pull requests.

Do: .github/workflows/backend.yml
- Triggers: pull_request and push to master, both with paths backend/** and .github/workflows/backend.yml; plus workflow_dispatch.
- Job test (all triggers, no AWS creds): ubuntu-latest, working-directory backend, actions/setup-python with 3.12, pip install -r requirements.txt -r requirements-dev.txt, then pytest.
- Job deploy: needs test; runs only when github.event_name != 'pull_request' and github.ref == 'refs/heads/master'. permissions: id-token: write, contents: read. concurrency group so deploys don't overlap.
  - aws-actions/configure-aws-credentials (role-to-assume: vars.AWS_DEPLOY_ROLE_ARN, aws-region: vars.AWS_REGION)
  - aws-actions/amazon-ecr-login
  - docker build backend/ and tag <registry>/<vars.ECR_REPOSITORY>:${{ github.sha }}; push it
  - Update the Express Mode service to the new image, only if vars.ECS_SERVICE_ARN != ''. This way the first run just pushes the image (the service is created by hand in L2). Use the command from the P2 notes. If it's unknown, check AWS docs. Don't guess; a failing, clearly-labelled step is better than a wrong one.
- Pin actions to major versions.

Files: .github/workflows/backend.yml (new)

Done when: the YAML is valid and the test job passes on the PR. The deploy job is skipped on PRs (it can only be fully exercised after C2).
```

Checklist

```text
Triggers + path filters (including the workflow file)
test job on Python 3.12
deploy job: OIDC, ECR login, build, push :sha
Service update gated on ECS_SERVICE_ARN
Deploy never runs on pull_request
PR opened and linked to this card
```

### C2 · Connect GitHub to AWS (OIDC role and repo variables)

Labels: `You`, `CI/CD` · Depends on: A0, A2, A3

Description

```text
Lets the workflow assume an AWS role without stored keys, but only from the master branch of this repo. Follow docs/deploy/RUNBOOK.md and infrastructure/policies/github-deploy-*.json.

Done when: the OIDC provider and theia-github-deploy-role exist (trust restricted to repo:SanAdams/project-theia:ref:refs/heads/master), and the repo variables are set. GitHub → Settings → Secrets and variables → Actions → Variables tab.
```

Checklist

```text
IAM → Identity providers → add OpenID Connect provider token.actions.githubusercontent.com, audience sts.amazonaws.com
Create theia-github-deploy-role with the trust + permissions policies
Repo variable AWS_REGION = us-west-2
Repo variable AWS_DEPLOY_ROLE_ARN = <role ARN>
Repo variable ECR_REPOSITORY = theia-backend
Leave ECS_SERVICE_ARN unset for now (set in L3)
```

---

## Epic: Launch

### Card titles

```text
L1 · Merge backend PRs and push the first image
L2 · Create the Express Mode service
L3 · Turn on automatic deploys
L4 · Point the Amplify site at the backend
L5 · Run end-to-end and security checks
L6 · Run the sizing experiment
```

### L1 · Merge backend PRs and push the first image

Labels: `You`, `Launch` · Depends on: B1–B5, C1, C2, P1

Description

```text
Merge order: B1 → B2 → B3 → B4, then B5 and C1. The merge to master triggers the workflow, which tests, builds and pushes the image. The deploy step is skipped because ECS_SERVICE_ARN is unset.

Done when: the Actions run is green and ECR theia-backend has an image tagged with the merge commit's SHA.
```

Checklist

```text
Merge B1, B2, B3, B4, B5, C1
Actions run green
Image :<sha> visible in ECR
```

### L2 · Create the Express Mode service

Labels: `You`, `Launch` · Depends on: L1, A1, A3, A4

Description

```text
Follow docs/deploy/RUNBOOK.md. Use the ECR image from L1.

Settings: port 8000 · health check /health · 1 vCPU / 2 GB · autoscaling min 1, max 2 (caps runaway cost) · roles from A3.

Environment variables:
AWS_REGION=us-west-2
IMAGES_BUCKET=<bucket from A1>
ENABLE_DEBUG_IMAGES=false
PRESIGNED_URL_TTL=3600
ALLOWED_ORIGINS=<Amplify URL, e.g. https://master.xxxx.amplifyapp.com, no trailing slash>
API_KEY=<key from A4>

Done when: the service is healthy, curl https://<service-url>/health returns 200, the log group retention is set to 30 days, and the service URL and ARN are recorded.
```

Checklist

```text
Create the service with the settings above
Wait for healthy
curl /health → 200
CloudWatch → Log groups → the service's group → retention 30 days
Record the service URL and ARN
```

### L3 · Turn on automatic deploys

Labels: `You`, `Launch` · Depends on: L2

Description

```text
Make the workflow's deploy step update the service.

Done when: a workflow run updates the service to the run's :<sha> image and the service stays healthy.
```

Checklist

```text
GitHub repo variable ECS_SERVICE_ARN = <service ARN>
Actions → backend workflow → Run workflow (master)
ECS console shows a new deployment with the :<sha> image
Service healthy afterwards
```

### L4 · Point the Amplify site at the backend

Labels: `You`, `Launch` · Depends on: L2, F1–F2 merged, A6

Description

```text
Expo inlines EXPO_PUBLIC_* at build time, so the front end must be rebuilt after setting these.

Amplify → App settings → Environment variables:
EXPO_PUBLIC_WEB_API_URL=<service URL, no trailing slash>
EXPO_PUBLIC_API_KEY=<key from A4>

Then rebuild: Amplify → master → Redeploy this version (or push any commit).

Done when: the Amplify build is green and the site loads after the password prompt.
```

Checklist

```text
Confirm A6 (site password) is on
Set EXPO_PUBLIC_WEB_API_URL
Set EXPO_PUBLIC_API_KEY
Rebuild the master branch
Site loads after password prompt
```

### L5 · Run end-to-end and security checks

Labels: `You` (an `Agent` can script the curl checks), `Launch` · Depends on: L4

Description

```text
Proves the whole system works and is locked down.

Done when every checklist item passes. Note anything that fails on the card.
```

Checklist

```text
Amplify URL in a private window prompts for password; curl of it without credentials → 401
curl https://<service>/health → 200
POST /api/v1/scan without X-API-Key → 401; with it → 200
Fetch from a non-Amplify origin in a browser is blocked by CORS
On the Amplify site: upload a photo → items, barcode images and crop gallery render
Browser console: no mixed-content or CORS errors
Crop and barcode URLs are signed S3 URLs; crops/ objects appear in the bucket
https://<service>/static/barcodes/<cic>.png → 404 (no barcodes in the image)
CloudWatch logs show the scan log lines
Budgets alarm active
```

### L6 · Run the sizing experiment

Labels: `You`, `Launch` · Depends on: L5

Description

```text
Find the cheapest size that's still fast enough. Use the same 3 test photos at each setting. Record the /scan time (browser DevTools → Network) and peak CPU/memory (ECS service → Metrics / CloudWatch) in this card.
```

Checklist

```text
Baseline 1 vCPU / 2 GB: record scan times + peak CPU/memory
Switch to 0.5 vCPU / 1 GB: record the same
Scale to zero (if min 0 is allowed): set to 0, then back to 1; record time until healthy
Decide the size and update the service
```

---

## Epic: Docs

### Card titles

```text
D1 · Update docs for the deployed setup
```

### D1 · Update docs for the deployed setup

Labels: `Agent`, `Docs` · Depends on: B1–B5 merged (F1–F2 for the front-end vars)

Description

```text
Read "Shared context" in docs/deploy/TASKS.md first.

Do:
- backend/.env.example: add IMAGES_BUCKET, PRESIGNED_URL_TTL, ENABLE_DEBUG_IMAGES, API_KEY, ALLOWED_ORIGINS (commented, with defaults) and set AWS_REGION=us-west-2.
- infrastructure/README.md: the IAM policy must include rekognition:DetectLabels as well as DetectText (it currently lists only DetectText). Point to infrastructure/policies/ and docs/deploy/RUNBOOK.md.
- CLAUDE.md: a "Deployment" section (Amplify front end + Express Mode backend, the pipeline, env vars on both sides, and that catalog edits deploy on push to master). Update the Mobile section: the web path now uses EXPO_PUBLIC_WEB_API_URL when set.
- docs/ARCHITECTURE.md: the storage seam (local disk vs S3, presigned URLs) and the debug flag.

Files: backend/.env.example, infrastructure/README.md, CLAUDE.md, docs/ARCHITECTURE.md

Done when: docs match the merged code (env var names checked against the source) and contain no real secrets, ARNs or account IDs.
```

Checklist

```text
.env.example
infrastructure/README.md (DetectLabels)
CLAUDE.md Deployment section + Mobile section
docs/ARCHITECTURE.md storage + debug flag
PR opened and linked to this card
```
