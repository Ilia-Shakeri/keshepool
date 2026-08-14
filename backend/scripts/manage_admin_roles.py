import argparse
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models import AdminIdentity, AdminRoleGrant
from app.services.admin_authorization_service import (
    ADMIN_ROLES,
    grant_admin_role,
    require_superadmin,
    revoke_admin_role,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage durable administrator role grants.")
    parser.add_argument("--actor-telegram-id", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    grant = commands.add_parser("grant")
    grant.add_argument("--target-telegram-id", required=True)
    grant.add_argument("--role", required=True, choices=sorted(ADMIN_ROLES))
    grant.add_argument("--display-name")
    revoke = commands.add_parser("revoke")
    revoke.add_argument("--target-telegram-id", required=True)
    revoke.add_argument("--role", required=True, choices=sorted(ADMIN_ROLES))
    commands.add_parser("list")
    return parser


async def _run(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as session:
        if args.command == "grant":
            changed = await grant_admin_role(
                session,
                actor_telegram_id=args.actor_telegram_id,
                target_telegram_id=args.target_telegram_id,
                role=args.role,
                display_name=args.display_name,
            )
            await session.commit()
            print("role grant added" if changed else "role grant already active")
            return
        if args.command == "revoke":
            changed = await revoke_admin_role(
                session,
                actor_telegram_id=args.actor_telegram_id,
                target_telegram_id=args.target_telegram_id,
                role=args.role,
            )
            await session.commit()
            print("role grant revoked" if changed else "active role grant not found")
            return
        await require_superadmin(session, args.actor_telegram_id)
        rows = await session.execute(
            select(AdminIdentity.telegram_id, AdminRoleGrant.role)
            .join(AdminRoleGrant, AdminRoleGrant.admin_identity_id == AdminIdentity.id)
            .where(
                AdminIdentity.is_active.is_(True),
                AdminRoleGrant.revoked_at.is_(None),
            )
            .order_by(AdminIdentity.telegram_id, AdminRoleGrant.role)
        )
        for telegram_id, role in rows.all():
            print(f"{telegram_id}\t{role}")


async def main() -> None:
    try:
        await _run(_parser().parse_args())
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
