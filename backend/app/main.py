import asyncio
import json
import hmac
import logging
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pythonjsonlogger import jsonlogger
from sqlalchemy import text

from app.api import admin, cashout, payments, products, users
from app.bot.handlers.admin_panel import admin_router
from app.bot.handlers.customer import customer_router
from app.bot.handlers.products_admin import products_router
from app.bot.handlers.transactions_admin import transactions_router
from app.bot.middleware import BlockBannedUserMiddleware
from app.bot.services.scheduler import start_scheduler
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, init_db
from app.core.redis import redis_client
from app.services.cache_service import redis_health
from app.services.telegram_inbox_service import enqueue_update

# Configure structured JSON logging
logger = logging.getLogger()
if logger.handlers:
    logger.handlers.clear()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

module_logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"


def _safe_webhook_info(bot_type: str, expected_url: str, info: object) -> dict[str, object]:
    actual_url = str(getattr(info, "url", "") or "")
    last_error_date = getattr(info, "last_error_date", None)
    if hasattr(last_error_date, "isoformat"):
        last_error_date = last_error_date.isoformat()
    return {
        "bot_type": bot_type,
        "configured": bool(actual_url),
        "url_matches_expected": hmac.compare_digest(actual_url, expected_url),
        "pending_update_count": getattr(info, "pending_update_count", 0),
        "last_error_date": last_error_date,
        "has_last_error": bool(getattr(info, "last_error_message", None)),
    }


def _webhook_request_fields(
    request: Request,
    bot_type: str,
    result: str,
    update_id: int | None = None,
    exception_class: str | None = None,
) -> dict[str, object]:
    fields: dict[str, object] = {
        "request_id": getattr(request.state, "request_id", None),
        "bot_type": bot_type,
        "telegram_update_id": update_id,
        "result": result,
    }
    if exception_class:
        fields["exception_class"] = exception_class
    return fields

# Initialize application bots and dispatchers
bot = Bot(token=settings.BOT_TOKEN)
customer_storage = RedisStorage.from_url(
    settings.REDIS_URL,
    key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
    state_ttl=settings.ADMIN_FSM_TTL_SECONDS,
    data_ttl=settings.ADMIN_FSM_TTL_SECONDS,
)
dp = Dispatcher(storage=customer_storage)
dp.update.outer_middleware(BlockBannedUserMiddleware())

admin_bot = Bot(token=settings.ADMIN_BOT_TOKEN)
admin_storage = RedisStorage.from_url(
    settings.REDIS_URL,
    key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
    state_ttl=settings.ADMIN_FSM_TTL_SECONDS,
    data_ttl=settings.ADMIN_FSM_TTL_SECONDS,
)
admin_dp = Dispatcher(storage=admin_storage)

# Register modular routers
dp.include_router(customer_router)
admin_dp.include_router(admin_router)
admin_dp.include_router(products_router)
admin_dp.include_router(transactions_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    polling_tasks: list[asyncio.Task] = []
    try:
        await init_db()
        if settings.TELEGRAM_BOT_MODE != "disabled":
            scheduler = start_scheduler(admin_bot)

        if settings.TELEGRAM_BOT_MODE == "webhook":
            module_logger.info("Telegram webhook transport enabled; configuration is managed separately.")
        elif settings.TELEGRAM_BOT_MODE == "polling":
            module_logger.info("Starting Telegram polling for local development.")
            await bot.delete_webhook(drop_pending_updates=False)
            await admin_bot.delete_webhook(drop_pending_updates=False)
            polling_tasks = [
                asyncio.create_task(dp.start_polling(bot, handle_signals=False)),
                asyncio.create_task(admin_dp.start_polling(admin_bot, handle_signals=False)),
            ]
        else:
            module_logger.info("Telegram bot transport disabled.")

        yield
    finally:
        if polling_tasks:
            for dispatcher in (dp, admin_dp):
                try:
                    await dispatcher.stop_polling()
                except RuntimeError:
                    pass
            await asyncio.gather(*polling_tasks, return_exceptions=True)

        if scheduler is not None:
            try:
                scheduler.shutdown()
            except Exception:
                module_logger.exception("Scheduler shutdown failed.")

        shutdown_steps = (
            ("main bot session", bot.session.close),
            ("admin bot session", admin_bot.session.close),
            ("customer FSM storage", customer_storage.close),
            ("admin FSM storage", admin_storage.close),
            ("Redis client", redis_client.aclose),
            ("database engine", engine.dispose),
        )
        for component, close_operation in shutdown_steps:
            try:
                await close_operation()
            except Exception:
                module_logger.exception("Shutdown failed for %s.", component)

production = settings.ENVIRONMENT.lower() == "production"
app = FastAPI(
    title="Keshepool API",
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_id
        if re.fullmatch(r"[A-Za-z0-9._:-]{8,64}", supplied_id)
        else uuid.uuid4().hex
    )
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Content-Type-Options"] = "nosniff"
    csp_header = (
        "Content-Security-Policy-Report-Only"
        if settings.CSP_REPORT_ONLY
        else "Content-Security-Policy"
    )
    response.headers[csp_header] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "form-action 'self'; "
        "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org; "
        "img-src 'self' data: https:; "
        "object-src 'none'; "
        "script-src 'self' https://telegram.org; "
        "style-src 'self' 'unsafe-inline'"
    )
    if production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Restrict CORS to the configured frontend origin only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_app_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=[
        "Content-Type",
        "X-Telegram-Init-Data",
        "X-Idempotency-Key",
    ],
)

# Mount API routers and static files
app.include_router(users.router)
app.include_router(products.router)
app.include_router(payments.router)
app.include_router(cashout.router)
if settings.ENABLE_INTERNAL_ADMIN_API:
    app.include_router(admin.router)

def _prepare_asset_root() -> Path:
    asset_root = Path(settings.ASSET_ROOT)
    asset_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=asset_root, prefix=".write-check-"):
            pass
    except OSError as exc:
        raise RuntimeError(f"Static asset directory is not writable: {asset_root}") from exc
    return asset_root


app.mount("/static", StaticFiles(directory=_prepare_asset_root()), name="static")

@app.get("/api/config")
async def get_public_config():
    support_username = settings.SUPPORT_TELEGRAM_USERNAME.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", support_username):
        support_username = ""
    return {
        "botUsername": settings.BOT_USERNAME,
        "supportUsername": support_username or None,
        "supportUrl": f"https://t.me/{support_username}" if support_username else None,
    }

@app.post(f"{WEBHOOK_PATH}/{{bot_type}}")
async def bot_webhook(
    bot_type: Literal["main", "admin"],
    request: Request, 
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    expected_secret = (
        settings.admin_telegram_webhook_secret
        if bot_type == "admin"
        else settings.main_telegram_webhook_secret
    )
    if not hmac.compare_digest(
        x_telegram_bot_api_secret_token or "",
        expected_secret,
    ):
        module_logger.warning(
            "Telegram webhook request rejected.",
            extra=_webhook_request_fields(request, bot_type, "rejected"),
        )
        raise HTTPException(status_code=401, detail="Invalid secret token.")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Webhook content type must be application/json.")

    update_id = None
    try:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                parsed_content_length = int(content_length)
                if parsed_content_length < 0:
                    raise HTTPException(status_code=400, detail="Invalid content length.")
                if parsed_content_length > settings.TELEGRAM_WEBHOOK_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="Webhook payload is too large.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid content length.") from exc
        chunks: list[bytes] = []
        body_size = 0
        async for chunk in request.stream():
            body_size += len(chunk)
            if body_size > settings.TELEGRAM_WEBHOOK_MAX_BYTES:
                raise HTTPException(status_code=413, detail="Webhook payload is too large.")
            chunks.append(chunk)
        update_data = json.loads(b"".join(chunks))
        if not isinstance(update_data, dict):
            raise HTTPException(status_code=400, detail="Webhook JSON body must be an object.")
        telegram_update = types.Update(**update_data)
        update_id = telegram_update.update_id
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        module_logger.warning(
            "Telegram webhook request ignored.",
            extra=_webhook_request_fields(
                request,
                bot_type,
                "ignored",
                exception_class=type(exc).__name__,
            ),
        )
        return {"status": "ignored"}

    try:
        async with AsyncSessionLocal() as session:
            inserted = await enqueue_update(
                session,
                bot_type=bot_type,
                update_id=telegram_update.update_id,
                payload=update_data,
            )
    except Exception as exc:
        module_logger.error(
            "Webhook inbox write failed.",
            extra=_webhook_request_fields(
                request,
                bot_type,
                "failed",
                update_id,
                type(exc).__name__,
            ),
        )
        raise HTTPException(status_code=503, detail="Webhook inbox is unavailable.") from exc
    module_logger.info(
        "Telegram webhook request accepted.",
        extra=_webhook_request_fields(
            request,
            bot_type,
            "queued" if inserted else "duplicate",
            update_id,
        ),
    )
    return {"status": "queued" if inserted else "duplicate"}

@app.get("/health")
@app.get("/health/live")
async def health_check():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    database_ok = False
    database_detail = "unavailable"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        database_ok = True
        database_detail = "ok"
    except Exception as exc:
        database_detail = type(exc).__name__
        module_logger.error("Database readiness check failed: %s", database_detail)

    redis_ok, redis_detail = await redis_health()
    payload = {
        "status": "ready" if database_ok and redis_ok else "degraded" if database_ok else "not_ready",
        "ready": database_ok,
        "checks": {
            "database": {"ok": database_ok, "detail": database_detail},
            "redis": {
                "ok": redis_ok,
                "detail": redis_detail,
                "required": False,
                "fallback": "database" if not redis_ok else None,
            },
        },
    }
    return JSONResponse(status_code=200 if database_ok else 503, content=payload)
