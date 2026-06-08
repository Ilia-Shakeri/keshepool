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
   git clone [https://github.com/your-repo/zoodsub.git](https://github.com/your-repo/zoodsub.git)
   cd zoodsub
Configure Environment Variables:
Update the docker-compose.yml file with your BOT_TOKEN and WEBHOOK_URL, or pass them via a .env file.

Start the Infrastructure:

Bash
docker-compose up -d --build
Run the Frontend locally (for development):

Bash
cd frontend
npm install
npm run dev