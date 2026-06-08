<div align="center">
  <h1>🚀 ZoodSub</h1>
  <p><b>A Modern Telegram Mini App (TWA) for Premium Digital Subscriptions</b></p>
  <p>
    <img src="https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js" alt="Next.js" />
    <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
    <img src="https://img.shields.io/badge/Telegram-Mini_App-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
  </p>
</div>

---

ZoodSub is a modern, high-performance Telegram Mini App designed for selling premium digital subscriptions (such as Spotify, Netflix, etc.) with seamless and instant delivery directly within Telegram.

## 🏗️ Architecture & Tech Stack

The project is built with a modern, scalable stack to ensure high availability and a smooth user experience:

* **Frontend**: Next.js 14, Tailwind CSS, Shadcn UI, Telegram Web App SDK
* **Backend**: FastAPI, Aiogram 3.x, PostgreSQL, Redis
* **Infrastructure**: Docker & Docker Compose

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed and configured on your local machine or server:

* 🐳 Docker and Docker Compose installed.
* 🤖 A Telegram Bot Token obtained securely from [@BotFather](https://t.me/BotFather).

---

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running for development and testing purposes.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Ilia-Shakeri/zoodsub.git](https://github.com/Ilia-Shakeri/zoodsub.git)
    cd zoodsub
    ```

2.  **Configure Environment Variables:**
    Update the `docker-compose.yml` file with your `BOT_TOKEN` and `WEBHOOK_URL`, or securely pass them via a `.env` file at the root of the project.

3.  **Start the Infrastructure:**
    ```bash
    docker-compose up -d --build
    ```

4.  **Run the Frontend locally (for development):**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

---

## 🛡️ DevOps & Security Notes

As part of our commitment to secure and reliable infrastructure, please adhere to the following operational guidelines:

* **Privilege Management**: The backend Docker container runs as a non-root user for enhanced security and container isolation.
* **Production Deployment**: The FastAPI webhook endpoint must be secured behind a reverse proxy (such as Nginx or Traefik) with valid SSL/TLS certificates enabled.