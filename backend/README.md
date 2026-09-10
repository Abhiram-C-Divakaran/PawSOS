# PawReach Backend MVP

## Architecture
Modular monolith using FastAPI, PostgreSQL + PostGIS, and SQLAlchemy.

## Running Locally

1. Setup environment variables:
   ```bash
   cp .env.example .env
   ```

2. Run with Docker Compose:
   ```bash
   docker compose up --build
   ```

3. Initialize the database and run migrations (inside the `backend` container, or locally if configured):
   ```bash
   # From the host, exec into the container
   docker exec -it pawsos_backend bash
   
   # Run alembic to create the initial tables
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```

4. Seed the database with demo data (inside the container):
   ```bash
   python seed.py
   ```

## Swagger UI
Available at `http://localhost:8000/docs`

## Features Included
- JWT Auth (Argon2 hashing)
- Role-Based Access Control (Citizen, Rescuer, Vet, Admin, etc.)
- Auto-Triage System for new Rescue Cases
- Dispatch/Rescuer Matching Logic
- Veterinary Treatment Records
- Full Case State Machine & Status Timeline
