# Launch Digital Campus today — free, worldwide

This is the launch plan. Every method below is **$0**. The split is intentional:

| Piece | Where it lives | Why |
| --- | --- | --- |
| Digital Campus (courses, attendance, assignments, exams, chat, hub, studio) | Public cloud | The world can reach it |
| KUDOS **on campus** | Same public app, `/kudos` | In-app guide for how to use the site |
| Superadmin | Same public app, `/admin/dashboard` | Unchanged. Admin-only. |
| KUDOS **HQ** (270 agents) | Your 4GB PC | Too heavy and quota-hungry for free cloud |
| LLM quota | Stays on the PC | Public campus help uses seeded docs, **zero API spend** |

Do **not** put the 270-agent farm, Ollama, Celery, Redis, or your Gemini/Groq/OpenAI keys on the public host. Render’s free box is 512MB. Your PC is 4GB. Both will die if HQ and the world share one machine.

```
                    students / lecturers / anyone
                                │
                    ┌───────────▼────────────┐
                    │  Vercel Hobby (free)   │  Next.js  →  your-app.vercel.app
                    └───────────┬────────────┘
                                │ /api  +  wss chat
                    ┌───────────▼────────────┐
                    │  Render free API       │  FastAPI  →  *.onrender.com
                    │  KUDOS campus help     │  Superadmin unchanged
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Neon Postgres (free)  │  data survives sleep/redeploy
                    └────────────────────────┘

     your 4GB PC  ── KUDOS HQ, 270 agents, quota keys ── optional private tunnel
```

---

## Method 1 — recommended for today

**Vercel (frontend) + Render (backend) + Neon (database)**

This is the only stack that is free, global, and launchable in about 30 minutes without a credit card on the compute hosts.

### 1. Neon — free database (5 minutes)

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the **pooled** connection string (`…-pooler…`, `sslmode=require`).
3. You now have persistent Postgres. Render’s free filesystem is wiped on every deploy, so do not use SQLite in public.

### 2. Render — free API (10 minutes)

1. [render.com](https://render.com) → New → Blueprint, or New → Web Service, connect this GitHub repo.
2. Settings:
   - **Build:** `pip install -r services/backend/requirements.txt`
   - **Start:** `bash services/backend/start.sh`
   - **Health check:** `/api/v1/health`
   - **Instance:** Free
3. Environment:

   | Key | Value |
   | --- | --- |
   | `SECRET_KEY` | Generate a long random string |
   | `DATABASE_URL` | Neon connection string |
   | `KUDOS_MODE` | `campus_help` |
   | `QUOTA_SAFE` | `true` |
   | `CORS_ORIGINS` | `*` for launch, then lock to your Vercel URL |
   | `DEBUG` | `false` |

4. Leave `GOOGLE_GEMINI_API_KEY`, `GROQ_API_KEY`, and `OPENAI_API_KEY` **empty**.
5. First boot runs `seed.py`, `seed_kudos.py`, and `seed_campus_help.py`.
6. Copy the URL, e.g. `https://digital-campus-api.onrender.com`.
7. First request after idle can take 30–60 seconds (free tier sleep). That is normal.

### 3. Vercel — free frontend (10 minutes)

1. [vercel.com](https://vercel.com) → Import GitHub repo.
2. **Root Directory:** `frontend`
3. Environment:

   | Key | Value |
   | --- | --- |
   | `BACKEND_URL` | `https://digital-campus-api.onrender.com` |
   | `NEXT_PUBLIC_API_URL` | same |
   | `NEXT_PUBLIC_WS_URL` | `wss://digital-campus-api.onrender.com` |

4. Deploy. Public URL: `https://your-project.vercel.app`.
5. Share that URL. That is the worldwide campus.

### 4. Superadmin (unchanged)

Login on the live site:

- Email: `admin@campus.edu`
- Password: `superadmin123`

Then open Superadmin → chat and run:

```
change password YOUR_NEW_PASSWORD
```

Dashboard, brain controls, root terminal, guardian, code agent, LLM config, and auto-learn stay exactly as they are. They are just hosted on Render now instead of `localhost`.

### 5. Your 4GB PC — KUDOS HQ only

On the PC, keep running HQ as you do today:

```bash
# services/backend/.env
KUDOS_MODE=hq
QUOTA_SAFE=true
# put Gemini / Groq keys HERE, not on Render
```

```bash
cd services/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Quota-safe mode tries **one** LLM at a time and stops on the first answer. It will not fan out to every key. Do not expose this process to the internet.

---

## Method 2 — Cloudflare Pages instead of Vercel

Same backend (Render + Neon). Frontend on [Cloudflare Pages](https://pages.cloudflare.com):

- Root: `frontend`
- Framework: Next.js
- Same `BACKEND_URL` / `NEXT_PUBLIC_WS_URL` as Method 1
- Unlimited CDN bandwidth, 500 builds/month, free custom domain

Use this if you want a Vercel alternative or more bandwidth headroom.

---

## Method 3 — Oracle Cloud Always Free (always on)

When Render’s 15-minute sleep is not acceptable.

- Always Free ARM VM, currently about **2 OCPU / 12GB RAM** (Oracle adjusted the older 4 / 24 offer). Still far more RAM than your PC.
- Credit card is usually required for identity check. You are not billed if you stay inside Always Free.
- Some regions return “out of capacity”. Try another region or upgrade the account to PAYG with a $1 budget alert — Always Free still does not charge if you stay in limits.

On the VM:

```bash
git clone git@github.com:mukondakangwa1-lgtm/New-project.git
cd New-project
export SECRET_KEY='a-long-random-string'
docker compose -f docker-compose.launch.yml up -d --build
```

Open `http://YOUR_PUBLIC_IP:3000`. Put nginx + Let’s Encrypt in front when you have a domain.

This compose file has **no Redis, no Celery, no 270 agents**. Campus KUDOS + Superadmin only.

---

## Method 4 — Hugging Face Spaces (fastest public demo)

1. New Docker Space at [huggingface.co/spaces](https://huggingface.co/spaces).
2. Use `services/backend/Dockerfile`.
3. Env: `KUDOS_MODE=campus_help`, `QUOTA_SAFE=true`.
4. You get `https://you-digital-campus.hf.space` for the API.

Good for a same-hour demo. Pair with Vercel if you still want the full UI.

---

## Method 5 — Cloudflare Tunnel (HQ only, not the world)

`cloudflared` is free. Use it so **you** can reach the 270-agent HQ on the PC without opening ports.

```bash
cloudflared tunnel login
cloudflared tunnel create kudos-hq
# route hq.yourdomain.com → http://127.0.0.1:8000
```

Do **not** give this URL to students. A 4GB box already running 270 agents cannot also be the public campus.

---

## Methods that are not free enough (skip today)

| Platform | Why not |
| --- | --- |
| Railway | Trial credit only, not a permanent free host |
| Fly.io | New accounts get a short trial, not a free tier |
| Heroku | Free tier removed |
| DigitalOcean App Platform | Static sites can be free; the API is paid |
| Serving the world from the 4GB PC | RAM + quota + residential IP will collapse |

---

## What stays where

**On the public campus (Methods 1–4)**

- Home, register, login, dashboard, courses
- Attendance, timetable, reports
- Assignments, exams, chat, hub, studio, media
- `/kudos` as the how-to-use-the-app guide
- Superadmin at `/admin/dashboard` — same screens, same commands

**On your PC**

- 270 agents
- Auto-learn / brain cycles that chew CPU
- LLM API keys and quota
- Optional private tunnel for you

**Quota rules baked into this launch**

- `QUOTA_SAFE=true` (default) queries one provider at a time
- Public `KUDOS_MODE=campus_help` answers from seeded help docs first
- No keys on Render means campus help costs **$0** even at world traffic

---

## Launch-day checklist

1. Push this branch (or merge to `main`) so Render/Vercel can see `render.yaml` and `frontend/`.
2. Create Neon → paste `DATABASE_URL`.
3. Deploy Render API → confirm `https://…onrender.com/api/v1/health` returns healthy.
4. Deploy Vercel with `BACKEND_URL` + `NEXT_PUBLIC_WS_URL`.
5. Open the Vercel URL on your phone (not just localhost).
6. Register a student account. Ask KUDOS: *“How do I take attendance?”*
7. Login as superadmin. Change the password. Leave HQ on the PC.
8. Post the Vercel URL. That is launch.

Default superadmin password is public in the README. Change it before you share the link.
