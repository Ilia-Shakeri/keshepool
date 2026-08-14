from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.check_repository_hygiene import rejection_reason


def test_repository_hygiene_rejects_private_and_generated_paths() -> None:
    assert rejection_reason(".env") is not None
    assert rejection_reason("ops/private.key") is not None
    assert rejection_reason("frontend/.next/server.js") is not None
    assert rejection_reason("release.tar.gz") is not None
    assert rejection_reason("backups/.gitkeep") is None
    assert rejection_reason(".env.example") is None
    assert rejection_reason("backend/app/main.py") is None


def test_source_export_is_allowlisted_scanned_and_non_overwriting() -> None:
    script = (ROOT / "scripts" / "export-source.sh").read_text(encoding="utf-8")

    assert "git archive" in script
    assert 'if [ -e "$output" ]' in script
    assert "command -v gitleaks" in script
    assert "gitleaks dir" in script
    assert "! -name '.env.example'" in script
    assert script.index("gitleaks dir") < script.index("tar -czf")
    assert ") -delete" not in script


def test_ci_builds_the_exported_source() -> None:
    pipeline = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    assert "source_export:" in pipeline
    assert "clean_export_build:" in pipeline
    assert "tar -xzf keshepool-source.tar.gz" in pipeline
    assert "docker build" in pipeline


def test_frontend_runtime_is_pinned_to_node_22() -> None:
    package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert (ROOT / "frontend" / ".nvmrc").read_text(encoding="utf-8").strip() == "22"
    assert '">=22 <23"' in package
    assert "FROM node:22-alpine" in dockerfile
    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "npm ci --legacy-peer-deps" in dockerfile
    assert "npm install" not in dockerfile
    assert "image: node:22-alpine" in (ROOT / ".gitlab-ci.yml").read_text(
        encoding="utf-8"
    )
