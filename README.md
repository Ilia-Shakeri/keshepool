# Keshepool

A modern Telegram Mini App (TWA) designed for purchasing premium accounts, VPN configurations (V2Ray), and managing financial services such as crypto and currency exchange.

## Features

- Seamless Telegram integration through the TWA SDK.
- Product catalog for premium accounts, VPN configs, and digital services.
- Wallet, orders, notifications, deposits, and cashout flows.
- Admin bot workflows for product and inventory management.
- Dockerized frontend, backend, PostgreSQL, and Redis services.

## Tech Stack

- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4, Shadcn UI, Lucide Icons.
- **Backend**: Python 3.11, FastAPI, Aiogram 3.x, SQLAlchemy, Asyncpg.
- **Database & Cache**: PostgreSQL 15, Redis 7.
- **Infrastructure**: Docker, Docker Compose.

## Project Structure

```text
keshepool/
+-- backend/              # FastAPI API, Aiogram bot, services, Alembic migrations
|   +-- alembic/          # Database migrations
|   +-- app/
|   |   +-- api/          # HTTP route modules
|   |   +-- bot/          # Telegram bot handlers, states, locales
|   |   +-- core/         # Config, database, Redis, security
|   |   +-- services/     # Business service functions
|   +-- requirements.txt
+-- frontend/             # Next.js Telegram Mini App
|   +-- public/           # Static fonts and logo assets
|   +-- src/
|       +-- app/          # Next.js App Router routes
|       +-- components/   # Shared layout and UI components
|       +-- features/     # Feature-specific frontend modules
|       +-- lib/          # API client and shared helpers
|       +-- types/        # Global TypeScript declarations
+-- docker-compose.yml    # Container orchestration
+-- .env.example          # Environment variables template
```

## Getting Started

Create a `.env` file in the root directory based on `.env.example`:

```bash
cp .env.example .env
```

Run the full stack with Docker Compose:

```bash
docker-compose up -d --build
```

Verify the deployment:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`

## Security Notes

- Telegram webhooks require HTTPS in deployed environments.
- Keep `.env` out of version control.
- Treat checkout account details and wallet/payment data as sensitive production data.
