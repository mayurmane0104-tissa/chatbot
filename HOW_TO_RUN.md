# HOW TO RUN — TissaTech AI Agent
# Complete step-by-step from scratch

=======================================================
STEP 1 — EXTRACT AND SETUP
=======================================================

1. Extract the zip file
2. Open PowerShell and navigate to the project:

   cd C:\path\to\tissatech-fixed

=======================================================
STEP 2 — CREATE .env FILE
=======================================================

Copy the example file:
   copy .env.example .env

Open .env in Notepad and fill in:
   POSTGRES_PASSWORD=MyStrongPass123!
   REDIS_PASSWORD=MyRedisPass123!
   DATABASE_URL=postgresql+asyncpg://tissatech:MyStrongPass123!@localhost:5432/tissatech
   REDIS_URL=redis://:MyRedisPass123!@localhost:6379/0
   CELERY_BROKER_URL=redis://:MyRedisPass123!@localhost:6379/1
   CELERY_RESULT_BACKEND=redis://:MyRedisPass123!@localhost:6379/2
   SECRET_KEY=any_random_64_chars_here
   NEXTAUTH_SECRET=any_random_32_chars_here
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   BEDROCK_AGENT_ID=your_agent_id (short ID only, not ARN)
   BEDROCK_AGENT_ALIAS_ID=your_alias_id
   BEDROCK_KNOWLEDGE_BASE_ID=your_kb_id

IMPORTANT: Use the SAME password in POSTGRES_PASSWORD and DATABASE_URL

=======================================================
STEP 3 — START DOCKER (Postgres + Redis only first)
=======================================================

   docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis

Wait 20 seconds. Verify both are healthy:
   docker ps

You should see: (healthy) next to postgres and redis

=======================================================
STEP 4 — SETUP PYTHON BACKEND
=======================================================

   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

=======================================================
STEP 5 — RUN DATABASE MIGRATIONS
=======================================================

Still inside backend/ with venv active:
   alembic upgrade head

You should see:
   Running upgrade -> 001_initial, Initial schema — all 14 tables

Verify tables exist:
   docker exec -it tissatech_postgres psql -U tissatech -d tissatech -c "\dt"
   (should show 14 tables)

=======================================================
STEP 6 — RUN BACKEND LOCALLY
=======================================================

Still inside backend/ with venv active:
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Open browser: http://localhost:8000/docs
You should see the Swagger API documentation.

=======================================================
STEP 7 — TEST BACKEND IS WORKING
=======================================================

Open these URLs in browser:
   http://localhost:8000/health              → {"status":"ok"}
   http://localhost:8000/api/v1/debug/config → shows your AWS config
   http://localhost:8000/api/v1/debug/db-test → shows 14 tables
   http://localhost:8000/api/v1/debug/bedrock-test → tests AWS Bedrock

=======================================================
STEP 8 — REGISTER FIRST USER
=======================================================

In Swagger (http://localhost:8000/docs):
   POST /api/v1/auth/register

Body:
   {
     "email": "admin@tissatech.com",
     "password": "Tissa@12345678",
     "full_name": "TissaTech Admin",
     "workspace_slug": "tissatech"
   }

Should return 201 with access_token and refresh_token.

=======================================================
STEP 9 — RUN FRONTEND
=======================================================

Open a NEW PowerShell window:
   cd C:\path\to\tissatech-fixed\frontend
   npm install
   npm run dev

Open browser: http://localhost:3000
You should see the TissaTech chat UI.

=======================================================
STEP 10 — TEST CHAT
=======================================================

Go to http://localhost:3000 and send a message.

If you see "Sorry, I encountered an error":
   - Check http://localhost:8000/api/v1/debug/bedrock-test
   - It will show the exact AWS error

=======================================================
TROUBLESHOOTING
=======================================================

ERROR: "Workspace not found"
→ Run: docker exec -it tissatech_postgres psql -U tissatech -d tissatech -c "SELECT slug FROM workspaces;"
→ Use exactly that slug in the register request (should be "tissatech")

ERROR: "Connection refused port 5432"
→ Docker postgres is not running. Run: docker compose -f infrastructure/docker/docker-compose.yml up -d postgres

ERROR: AWS/Bedrock errors
→ Open http://localhost:8000/api/v1/debug/bedrock-test
→ It shows the exact error (wrong credentials, wrong ID, no permissions, etc.)

ERROR: "Invalid enum value"
→ Old code is cached. Stop uvicorn, run: Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
→ Then restart uvicorn

=======================================================
RUNNING FULL DOCKER STACK (optional - after everything works locally)
=======================================================

   docker compose -f infrastructure/docker/docker-compose.yml up -d

Access at: http://localhost (port 80 via Nginx)

=======================================================
MONITORING (PROMETHEUS / GRAFANA / ALERTS)
=======================================================

After full stack is up:

1. Prometheus:
   http://localhost:9090

2. Alertmanager:
   http://localhost:9093

3. Grafana:
   http://localhost:3001
   username: admin
   password: value of GRAFANA_PASSWORD from your .env

Grafana auto-loads:
- TissaTech Overview
- TissaTech Crawl & Celery
