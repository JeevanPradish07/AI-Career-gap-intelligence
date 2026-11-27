# 🎯 AI-Based Personalized Career Skill Gap Intelligence Platform

> AI-powered platform that analyzes resumes, computes skill gaps vs industry benchmarks, matches jobs via FAISS, and generates personalized 12-week learning roadmaps with INR salary projections.

---

## 🔑 API Keys You Need (Read This First)

### 1. HuggingFace API Key — REQUIRED
**Get from**: https://huggingface.co/settings/tokens

Steps:
1. Go to https://huggingface.co → Create free account
2. Click your avatar → Settings → Access Tokens
3. Click **"New token"** → Name: `career-platform` → Role: **Read**
4. Copy the token (starts with `hf_...`)
5. Paste into `backend/.env` as `HUGGINGFACE_API_KEY=hf_xxxxx`

**What it's used for** (3 models, all free on HuggingFace Inference API):
| Phase | Model | Purpose |
|-------|-------|---------|
| 2.1   | `dslim/bert-base-NER` | Extract tech skills from resume |
| 2.2   | `cross-encoder/nli-deberta-v3-small` | Score proficiency level per skill |
| 2.4   | `sentence-transformers/all-mpnet-base-v2` | Generate 768-dim embeddings |

> ✅ All 3 models run on HuggingFace's servers — no GPU needed on your machine.

---

### 2. RapidAPI Key — REQUIRED for Phase 6 (Course Search)
**Get from**: https://rapidapi.com

Steps:
1. Go to https://rapidapi.com → Sign up free (takes 2 min)
2. Search: `"Udemy Courses"` in the marketplace
3. Subscribe to the **free plan** (100 req/day)
4. Go to your "Apps" tab → copy the API key
5. Paste into `backend/.env` as `RAPIDAPI_KEY=xxxxx`

> ✅ Free tier (100 req/day) is enough for development.
> ✅ Falls back to `ml_data/courses_fallback/courses_fallback.json` if API fails.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+  → https://python.org/downloads
- Node.js 20 LTS → https://nodejs.org
- Docker Desktop → https://docker.com/products/docker-desktop

### Step 1 — Start Database & Redis
```bash
docker-compose up -d
```

### Step 2 — Setup Backend
```bash
cd backend
cp .env.example .env
# ← Edit .env and add your HuggingFace + RapidAPI keys

pip install -r requirements.txt
python -m spacy download en_core_web_sm

uvicorn main:app --reload --port 8000
```

### Step 3 — Build Job Corpus (One-Time)
```bash
pip install datasets sentence-transformers faiss-cpu
python scripts/build_job_corpus.py
# This downloads ~19K job descriptions from HuggingFace and builds the FAISS index
# Takes ~20-30 minutes on first run, then saved permanently
```

### Step 4 — Start Celery Worker
```bash
cd backend
celery -A core.celery_app worker --loglevel=info
```

### Step 5 — Setup Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- pgAdmin (DB viewer): http://localhost:5050

---

## 📁 Project Structure

```
career-skill-gap-platform/
├── backend/
│   ├── main.py                          # FastAPI entry point
│   ├── requirements.txt
│   ├── .env.example                     # ← Copy to .env and add your keys
│   ├── core/
│   │   ├── config.py                    # All environment variable bindings
│   │   ├── security.py                  # JWT auth
│   │   └── celery_app.py               # Task queue config
│   ├── phases/
│   │   ├── phase1_ingestion/            # PDF parsing, PII scrub, profile detect
│   │   ├── phase2_nlp/                  # HuggingFace NER + proficiency + embeddings
│   │   ├── phase3_benchmark/            # Industry benchmark compare + resume audit
│   │   ├── phase4_career_match/         # FAISS job matching, career pathway
│   │   ├── phase5_gap_scoring/          # R(u,r) formula, E(u) score, gap categories
│   │   ├── phase6_roadmap/              # 12-week roadmap + course fetching
│   │   └── phase7_report/              # Report assembly + telemetry
│   └── services/
│       ├── hf_service.py               # HuggingFace API client (3 models)
│       └── course_service.py           # RapidAPI course client + fallback
├── frontend/                            # React 18 + Vite (TODO: initialize)
├── ml_data/
│   ├── industry_benchmarks/             # Required skills per role
│   ├── career_pathways/                 # Role progression graphs
│   ├── salary_data/                     # INR salary ranges
│   ├── job_vectors/                     # FAISS index (built by script)
│   ├── tech_modernity_db/               # Modern vs outdated tech list
│   └── courses_fallback/               # Curated courses when API fails
├── scripts/
│   └── build_job_corpus.py             # One-time: builds FAISS index
└── docker-compose.yml                   # PostgreSQL + Redis + pgAdmin
```

---

## 🧮 Key Formulas

### Employability Score E(u) — 0 to 100
```
E(u) = 0.40 × SkillMatch
     + 0.25 × ProficiencyDepth
     + 0.20 × TrendAlignment
     + 0.15 × ProfileCompleteness
```

### Readiness Formula R(u,r) — 0 to 1
```
R(u,r) = Σ w_s · [α·(P_u/P_r) + (1-α)·max(Sim·P_u/P_r·e^{-λΔt})] · D(s)
```

### Recency Decay
```
RecencyFactor = e^{-λΔt}   where λ=0.15, Δt = years since last used
```

---

## 📊 Score Interpretation

| Score | Label | Meaning |
|-------|-------|---------|
| 80–100 | 🟢 Highly Employable | Ready for Tier A roles now |
| 60–79  | 🟡 Employable | Ready for Tier B, stretch for Tier A |
| 40–59  | 🟠 Developing | Needs 2–3 critical skills |
| 0–39   | 🔴 Early Stage | Student/fresher baseline |
