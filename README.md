# Keshepool 💸

A modern Telegram Mini App (TWA) designed for purchasing premium accounts, VPN configurations (V2Ray), and managing financial services (crypto/currency exchange).

## 🌟 Features

* **Seamless Telegram Integration**: Fully functional within Telegram using the TWA SDK.
* **Extensive Product Catalog**: Premium accounts (Spotify, Netflix, PS Plus, etc.), custom VPN configs, and social media upgrades (Telegram Premium, Discord Nitro).
* **Financial Services**: Crypto and foreign currency payment processing via Tetra98 API.
* **Gamification**: Interactive daily spin wheel for user discounts and retention.
* **Modern UI/UX**: Built with Next.js, Tailwind CSS, and Shadcn UI using the product's dark/red theme.

## 🛠 Tech Stack

* **Frontend**: Next.js 16, React 19, Node.js 22, Tailwind CSS, Lucide Icons.
* **Backend**: Python 3.11, FastAPI, Aiogram 3.x, SQLAlchemy, Asyncpg.
* **Database & Cache**: PostgreSQL 15, Redis 7.
* **Infrastructure**: Docker, Docker Compose.

## 📂 Project Structure

```text
keshepool/
├── backend/           # FastAPI & Aiogram Bot
│   ├── app/           # Application source code
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/          # Next.js Telegram Mini App
│   ├── src/           # Components, UI, and Pages
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml # Container orchestration
└── .env.example       # Environment variables template
```

## 🚀 Getting Started

### 1. Prerequisites

* [Docker](https://docs.docker.com/get-docker/) and Docker Compose installed on your host.
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather).

### 2. Environment Setup

Create a `.env` file in the root directory based on `.env.example`:

```bash
cp .env.example .env
```

Update the `.env` file with your specific credentials:

```env
# Backend Configuration
BOT_TOKEN=your_telegram_bot_token
WEBHOOK_URL=https://your-domain.com
WEB_APP_URL=https://your-domain.com

# Database Configuration (Docker Internal)
POSTGRES_USER=keshepool_user
POSTGRES_PASSWORD=keshepool_password
POSTGRES_DB=keshepool_db

# Tetra98 Third-Party Reseller API
TETRA98_API_URL=https://tetra98.com
TETRA98_API_KEY=your_api_key_here

# Explicit admin allowlist
ADMIN_TELEGRAM_IDS=123456789
ADMIN_API_KEY=your_internal_admin_api_key
```

### 3. Run the Stack

For a source checkout, Compose builds the backend and frontend images locally when `--build` is used:

```bash
docker network create caddy_gateway_net
docker compose up -d --build --force-recreate
```

Production uses only `sh ./deploy.sh` with one non-zero full Git SHA for both registry images. The script verifies image IDs and the frontend revision before cutover completes.

### 4. Verify Deployment

* **Frontend**: Accessible through the configured HTTPS reverse proxy.
* **Liveness**: `GET /health/live`.
* **Readiness**: `GET /health/ready`.
* **Routing smoke checks**: `sh ./smoke.sh`.

Production releases use immutable registry images tagged with the same full commit SHA. See [DEPLOYMENT.md](DEPLOYMENT.md) for ingress, CI variables, release, and rollback details.

## 🔒 Security Notes

* Ensure your `WEBHOOK_URL` is secured with an SSL certificate (HTTPS), as this is strictly required by Telegram for Webhooks.
* Keep your `.env` file out of version control.
* Export shared source only with `sh ./scripts/export-source.sh`; CI scans commits for secrets.
* Keep host `vm.overcommit_memory = 1` persistent for Redis. Containers do not change host kernel settings.
* Information entered in the "Personal Account" checkout flow is sensitive; ensure proper encryption in your database layer before moving to production.
