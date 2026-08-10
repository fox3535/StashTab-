@echo off
cd /d "%~dp0"
docker compose up -d
cd services\api
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
if not exist .env copy .env.example .env
start "Mimir API" cmd /k uvicorn app.main:app --reload --port 8001
cd ..\..
start "Mimir Web" cmd /k npm run dev
echo Started Postgres, API :8001, and Next.js :3000
