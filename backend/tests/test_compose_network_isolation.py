import re
from pathlib import Path


COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _top_level_block(source: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}:\s*$\n(?P<body>.*?)(?=^[^ \r\n][^\r\n]*:\s*$|\Z)",
        source,
    )
    assert match is not None, f"missing top-level {heading!r} block"
    return match.group("body")


def _named_block(source: str, name: str, *, indent: int) -> str:
    prefix = " " * indent
    match = re.search(
        rf"(?ms)^{prefix}{re.escape(name)}:\s*$\n(?P<body>.*?)(?=^{prefix}[^ \r\n][^\r\n]*:\s*$|\Z)",
        source,
    )
    assert match is not None, f"missing {name!r} block"
    return match.group("body")


def _service_networks(services: str, service_name: str) -> set[str]:
    service = _named_block(services, service_name, indent=2)
    match = re.search(
        r"(?ms)^    networks:\s*$\n(?P<body>.*?)(?=^    [^ \r\n][^\r\n]*:\s*|\Z)",
        service,
    )
    if match is None:
        return set()
    return set(re.findall(r"(?m)^      - ([A-Za-z0-9_.-]+)\s*$", match.group("body")))


def test_compose_enforces_network_isolation_contract():
    source = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "keshepool_internal_net" not in source
    services = _top_level_block(source, "services")

    expected_networks = {
        "db": {"keshepool_data_net"},
        "db-backup": {"keshepool_data_net"},
        "redis": {"keshepool_data_net"},
        "migrate": {"keshepool_data_net"},
        "backend": {"keshepool_data_net", "caddy_gateway_net"},
        "telegram-worker": {
            "keshepool_data_net",
            "keshepool_worker_egress_net",
        },
        "telegram-configure": {"keshepool_worker_egress_net"},
        "frontend": {"caddy_gateway_net"},
    }
    assert {
        name: _service_networks(services, name) for name in expected_networks
    } == expected_networks

    for service_name in ("db", "db-backup", "redis", "migrate"):
        service = _named_block(services, service_name, indent=2)
        assert "ports:" not in service
        assert "network_mode:" not in service

    static_init = _named_block(services, "static-init", indent=2)
    assert 'network_mode: "none"' in static_init
    assert "networks:" not in static_init

    networks = _top_level_block(source, "networks")
    data_network = _named_block(networks, "keshepool_data_net", indent=2)
    assert re.search(r"(?m)^    internal: true\s*$", data_network)

    egress_network = _named_block(
        networks,
        "keshepool_worker_egress_net",
        indent=2,
    )
    assert re.search(r"(?m)^    driver: bridge\s*$", egress_network)
    assert "internal:" not in egress_network
    assert "external:" not in egress_network

    gateway_network = _named_block(networks, "caddy_gateway_net", indent=2)
    assert re.search(r"(?m)^    external: true\s*$", gateway_network)


def test_short_lived_jobs_have_minimum_network_and_secret_scope():
    source = COMPOSE_PATH.read_text(encoding="utf-8")
    services = _top_level_block(source, "services")

    migrate = _named_block(services, "migrate", indent=2)
    assert "REDIS_URL=" not in migrate
    assert "${BOT_TOKEN}" not in migrate
    assert "${ADMIN_BOT_TOKEN}" not in migrate
    assert "TELEGRAM_BOT_MODE=disabled" in migrate

    configure = _named_block(services, "telegram-configure", indent=2)
    assert "depends_on:" not in configure
    assert "@db:5432" not in configure
    assert "redis://redis:6379" not in configure
    assert "TETRA98_API_KEY" not in configure
    assert "CRYPTO_WEBHOOK_SECRET" not in configure


def test_frontend_runtime_is_read_only_and_resource_bounded():
    source = COMPOSE_PATH.read_text(encoding="utf-8")
    services = _top_level_block(source, "services")
    frontend = _named_block(services, "frontend", indent=2)

    assert re.search(r"(?m)^    read_only: true\s*$", frontend)
    assert re.search(r"(?ms)^    cap_drop:\s*$\n      - ALL\s*$", frontend)
    assert "no-new-privileges:true" in frontend
    assert re.search(r"(?m)^    pids_limit: 200\s*$", frontend)
    assert re.search(r"(?m)^    mem_limit: 512m\s*$", frontend)
    assert re.search(r"(?m)^    cpus: 1\.0\s*$", frontend)
    assert "/tmp:rw,noexec,nosuid,size=64m" in frontend
    assert "/app/.next/cache:rw,noexec,nosuid,size=64m" in frontend


def test_deploy_recreates_worker_during_network_cutover():
    deploy = (COMPOSE_PATH.parent / "deploy.sh").read_text(encoding="utf-8")

    assert "docker compose stop telegram-worker" in deploy
    assert "--force-recreate telegram-worker" in deploy
    assert 'verify_running_image telegram-worker "$BACKEND_IMAGE"' in deploy


def test_minimum_migration_settings_are_valid():
    from app.core.config import Settings

    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://db:db@db:5432/db",
        BOT_TOKEN="migration-not-used",
        ADMIN_BOT_TOKEN="migration-not-used",
        TELEGRAM_BOT_MODE="disabled",
        WEB_APP_URL="https://migration.invalid",
        ENVIRONMENT="migration",
    )
    assert config.TELEGRAM_BOT_MODE == "disabled"


def test_minimum_telegram_configuration_settings_are_valid():
    from app.core.config import Settings

    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
        REDIS_URL="redis://127.0.0.1:1/0",
        BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        ADMIN_BOT_TOKEN="987654321:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        TELEGRAM_BOT_MODE="webhook",
        WEBHOOK_URL="https://config.invalid",
        WEB_APP_URL="https://config.invalid",
        MAIN_TELEGRAM_WEBHOOK_SECRET="main-test-secret",
        ADMIN_TELEGRAM_WEBHOOK_SECRET="admin-test-secret",
        ADMIN_TELEGRAM_IDS="1",
        ADMIN_GROUP_CHAT_ID="-100123456",
        ADMIN_REQUIRE_GROUP_ADMIN=True,
        USDT_TO_IRR_RATE=1,
        TRUSTED_PROXY_IPS="127.0.0.1",
        ENVIRONMENT="production",
    )
    assert config.DATABASE_URL.endswith("@127.0.0.1:1/unused")
