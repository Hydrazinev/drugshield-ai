# Railway Deploy (Backend + Frontend)

This repo is configured for two Railway services:

- `backend` service (FastAPI)
- `frontend` service (Next.js)

Each service uses its own `railway.json` in that folder.

## 1. Create Backend Service

1. In Railway, create a new service from this repo.
2. Set **Root Directory** to `backend`.
3. Railway will use `backend/railway.json`.
4. Add environment variables:
   - `OPENAI_API_KEY=...`
   - `OPENAI_MODEL=gpt-5.2` (optional)
5. Deploy.
6. Copy backend public URL, e.g. `https://drugshield-backend.up.railway.app`.

## 2. Create Frontend Service

1. Create another Railway service from the same repo.
2. Set **Root Directory** to `frontend`.
3. Railway will use `frontend/railway.json`.
4. Add environment variable:
   - `NEXT_PUBLIC_BACKEND_URL=https://<your-backend-url>`
5. Deploy.

## 3. Verify

- Backend health: `https://<backend-url>/health`
- Frontend load: `https://<frontend-url>/`
- Run one medication analysis from UI.

## Notes

- Production backend run is non-reload (already configured).
- If frontend cannot reach backend, re-check `NEXT_PUBLIC_BACKEND_URL` and redeploy frontend.
