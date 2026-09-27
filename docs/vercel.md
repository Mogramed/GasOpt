# Deploy GasOps on Vercel

GasOps deploys as one Vercel project: Vite serves the React application and the
Python runtime exposes the FastAPI application under `/api/*`. Both layers share
one origin, matching the existing frontend API calls.

## Import from GitHub

1. Open <https://vercel.com/new> and grant Vercel access to the private
   `Mogramed/GasOpt` repository if it is not already listed.
2. Import `Mogramed/GasOpt`. Keep the repository root as the Root Directory.
3. Leave the versioned build settings unchanged. `vercel.json` installs and
   builds `frontend/`, publishes `frontend/dist`, and configures the Python
   function at `api/index.py`.
4. Deploy. No Dune key or other environment variable is required: the validated
   runtime snapshot is committed with the project.

After deployment, verify these URLs, replacing the hostname with the Vercel URL:

- `/api/v1/health` returns `status: ok` and the dataset identity;
- `/overview` loads directly, confirming SPA deep links;
- `/optimizer` can load an archived result and run a TRAIN-only solve;
- `/results` displays the frozen TEST evaluation.

Every push to `main` will create a new production deployment when the Vercel
Git integration is enabled. Pull requests and non-production branches create
preview deployments under the normal Vercel Git workflow.

## Versioned deployment contract

- `.python-version` fixes Python 3.12 for the scientific wheels.
- `api/index.py` exports the existing FastAPI `app` and fixes the repository root
  before the immutable study snapshot loads.
- `vercel.json` builds Vite, preserves React Router deep links, includes the
  required scientific snapshot, excludes research/build folders from the Python
  function, and allows up to 60 seconds for a solve request.
- The root `package.json` gives Vercel a stable monorepo entrypoint; install,
  build and development commands then delegate to `frontend/` explicitly.
- Only the four verified processed files and the small root-level empirical
  archive are committed. Raw Dune exports and plot folders remain excluded.

The function filesystem is read-only and instances are ephemeral. GasOps already
uses immutable inputs; only the bounded in-memory solve cache is lost on a cold
start. A new instance reloads and audits the same archived study. No user result
is persisted, and no Dune API call occurs at runtime.

## Optional CLI check

With a Vercel account authenticated locally, run from the repository root:

```powershell
npx vercel dev
```

For a preview deployment use `npx vercel`; for production use `npx vercel --prod`.
The GitHub import is preferred because later pushes deploy automatically.
