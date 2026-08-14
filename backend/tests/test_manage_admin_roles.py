import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "manage_admin_roles.py"
    spec = importlib.util.spec_from_file_location("manage_admin_roles", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_role_cli_requires_explicit_actor_target_and_known_role():
    parser = _module()._parser()
    args = parser.parse_args(
        [
            "--actor-telegram-id",
            "100",
            "grant",
            "--target-telegram-id",
            "200",
            "--role",
            "finance",
        ]
    )
    assert (args.command, args.actor_telegram_id, args.target_telegram_id, args.role) == (
        "grant",
        "100",
        "200",
        "finance",
    )
