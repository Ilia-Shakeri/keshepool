# ZoodSub

ZoodSub is a modern, full-stack Telegram Mini App designed for selling premium digital subscriptions (Spotify, Netflix, Apple Music, etc.) via an automated, lightning-fast bot interface. 

Built with scalability in mind, it utilizes a Next.js frontend integrated directly into Telegram, powered by a robust Python FastAPI backend, PostgreSQL for data persistence, and Redis for caching and background tasks.

## 🛠 Tech Stack

**Frontend:**
- [Next.js 14+ (App Router)](https://nextjs.org/)
- [React](https://react.dev/) & [Tailwind CSS](https://tailwindcss.com/)
- [shadcn/ui](https://ui.shadcn.com/) components
- Telegram Web App SDK (`@twa-dev/sdk`)

**Backend:**
- [Python 3.11](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) (High-performance web framework)
- [Aiogram 3.x](https://docs.aiogram.dev/) (Asynchronous Telegram Bot API)
- [PostgreSQL](https://www.postgresql.org/) + `asyncpg` + `SQLAlchemy`
- [Redis](https://redis.io/)

**DevOps & Infrastructure:**
- Docker & Docker Compose
- Multi-stage container builds
- Nginx / Traefik ready

## 🚀 Quick Start (Development)

### Prerequisites
- Docker and Docker Compose installed.
- A Telegram Bot Token (Get one from [@BotFather](https://t.me/BotFather)).

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Ilia-Shakeri/ZoodSub.git](https://github.com/Ilia-Shakeri/ZoodSub.git)
   cd ZoodSub
    ```
2. **Configure Environment Variables:**
Create a `.env` file in the root directory:
    ```env
    BOT_TOKEN=your_telegram_bot_token_here
    WEBHOOK_URL=[https://your-ngrok-or-production-domain.com](https://your-ngrok-or-production-domain.com)
    ```


3. **Spin up the infrastructure:**
    ```bash
    docker-compose up -d --build
    ```


4. **Verify the services:**
* Frontend: `http://localhost:3000`
* Backend API: `http://localhost:8000/health`
* Database: Accessible on `localhost:5432`



## 📂 Project Structure

* `/frontend` - Next.js application tailored for Telegram Web App UI.
* `/backend` - FastAPI application managing webhooks, payments, and bot logic.
* `docker-compose.yml` - Orchestration for seamless full-stack deployment.

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.