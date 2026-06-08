
# ZoodSub - Telegram Mini App (TWA)

ZoodSub is a modern Telegram Mini App designed for selling premium digital subscriptions (Spotify, Netflix, etc.) with instant delivery. 

## Architecture

The project is built with a modern, scalable stack:
* **Frontend**: Next.js 14, Tailwind CSS, Shadcn UI, Telegram Web App SDK.
* **Backend**: FastAPI, Aiogram 3.x, PostgreSQL, Redis.
* **Infrastructure**: Docker & Docker Compose.

## Prerequisites

* Docker and Docker Compose installed on your machine.
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather).

## Getting Started

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-repo/zoodsub.git](https://github.com/Ilia-Shakeri/zoodsub.git)
   cd zoodsub

2. **Configure Environment Variables:**
Update the `docker-compose.yml` file with your `BOT_TOKEN` and `WEBHOOK_URL`, or pass them via a `.env` file.
3. **Start the Infrastructure:**
   ```bash
   docker-compose up -d --build
   ```


4. **Run the Frontend locally (for development):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```



## DevOps Notes

* The backend Docker container runs as a non-root user for enhanced security.
* In production, the FastAPI webhook endpoint should be secured behind a reverse proxy (like Nginx or Traefik) with SSL/TLS enabled.

