import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.services.credential_vault import (
    CredentialVaultError,
    credential_cipher_from_settings,
)
from app.services.credential_vault_migration import (
    CredentialVaultBatchReport,
    CredentialVaultOperationError,
    backfill_credential_vault_batch,
    count_credential_vault_rows,
    finalize_credential_vault_batch,
    verify_credential_vault_batch,
)


def _add_batch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage and verify the inventory credential vault without emitting values."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("count", help="Count vault states without loading credentials or keys.")
    backfill = commands.add_parser("backfill")
    _add_batch_arguments(backfill)
    verify = commands.add_parser("verify")
    _add_batch_arguments(verify)
    finalize = commands.add_parser("finalize")
    _add_batch_arguments(finalize)
    return parser


def _empty_summary(operation: str, applied: bool, cursor: int) -> dict[str, object]:
    return {
        "operation": operation,
        "applied": applied,
        "batches": 0,
        "scanned": 0,
        "eligible": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "quarantined": 0,
        "skipped": 0,
        "next_after_id": cursor,
        "done": False,
    }


def _merge_report(
    summary: dict[str, object],
    report: CredentialVaultBatchReport,
) -> None:
    summary["batches"] = int(summary["batches"]) + 1
    for field in (
        "scanned",
        "eligible",
        "valid",
        "invalid",
        "duplicates",
        "quarantined",
        "skipped",
    ):
        summary[field] = int(summary[field]) + int(getattr(report, field))
    summary["next_after_id"] = report.last_id
    summary["done"] = report.done


async def _run_batches(
    args: argparse.Namespace,
    operation: Callable[..., Awaitable[CredentialVaultBatchReport]],
    **operation_options: object,
) -> dict[str, object]:
    if not 1 <= args.max_batches <= 10_000:
        raise CredentialVaultOperationError("Max batches must be between 1 and 10000.")
    cipher = credential_cipher_from_settings(settings)
    cursor = args.after_id
    summary = _empty_summary(args.command, args.apply, cursor)
    known_fingerprints: set[bytes] | None = (
        set() if args.command == "backfill" else None
    )
    async with AsyncSessionLocal() as session:
        for _ in range(args.max_batches):
            options = dict(operation_options)
            if known_fingerprints is not None:
                options["known_fingerprints"] = known_fingerprints
            report = await operation(
                session,
                cipher,
                after_id=cursor,
                batch_size=args.batch_size,
                apply=args.apply,
                confirmation=args.confirm,
                **options,
            )
            if args.apply:
                await session.commit()
            else:
                await session.rollback()
            _merge_report(summary, report)
            cursor = report.last_id
            if report.done:
                break
    return summary


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "count":
        async with AsyncSessionLocal() as session:
            counts = await count_credential_vault_rows(session)
        return {"operation": "count", **counts.to_dict()}
    if args.command == "backfill":
        return await _run_batches(args, backfill_credential_vault_batch)
    if args.command == "verify":
        return await _run_batches(args, verify_credential_vault_batch)
    return await _run_batches(
        args,
        finalize_credential_vault_batch,
        finalization_enabled=settings.CREDENTIAL_VAULT_FINALIZE_ENABLED,
    )


async def main() -> int:
    args = _parser().parse_args()
    try:
        output = await _run(args)
    except (CredentialVaultError, CredentialVaultOperationError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "failed"}, sort_keys=True))
        return 1
    finally:
        await engine.dispose()
    print(json.dumps({"status": "ok", **output}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
