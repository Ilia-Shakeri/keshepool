import hashlib
import io
import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


MAX_UPLOAD_BYTES = 2_000_000
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096
MAX_IMAGE_PIXELS = 16_000_000
MAX_ENCODED_BYTES = 4_000_000
_OWNED_ASSET_NAME = re.compile(r"^[0-9a-f]{64}\.webp$")


class ProductAssetError(ValueError):
    pass


@dataclass(frozen=True)
class StoredProductAsset:
    url: str
    path: Path
    created: bool


def _validate_dimensions(image: Image.Image) -> None:
    width, height = image.size
    if (
        width < 1
        or height < 1
        or width > MAX_IMAGE_WIDTH
        or height > MAX_IMAGE_HEIGHT
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise ProductAssetError("image_dimensions")


def sanitize_product_image(file_bytes: bytes) -> bytes:
    if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ProductAssetError("logo_too_large")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(file_bytes)) as probe:
                if probe.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ProductAssetError("image_required")
                if getattr(probe, "n_frames", 1) != 1:
                    raise ProductAssetError("image_required")
                _validate_dimensions(probe)
                probe.verify()

            with Image.open(io.BytesIO(file_bytes)) as source:
                _validate_dimensions(source)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                _validate_dimensions(oriented)
                has_alpha = "A" in oriented.getbands() or (
                    oriented.mode == "P" and "transparency" in oriented.info
                )
                clean = oriented.convert("RGBA" if has_alpha else "RGB")

            output = io.BytesIO()
            clean.save(
                output,
                format="WEBP",
                quality=85,
                method=6,
                exact=True,
            )
    except ProductAssetError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ) as exc:
        raise ProductAssetError("image_required") from exc

    encoded = output.getvalue()
    if not encoded or len(encoded) > MAX_ENCODED_BYTES:
        raise ProductAssetError("image_dimensions")
    return encoded


def _asset_directory() -> Path:
    root = Path(settings.ASSET_ROOT).resolve()
    asset_dir = (root / "product-assets").resolve()
    if root not in asset_dir.parents:
        raise ProductAssetError("image_required")
    asset_dir.mkdir(parents=True, exist_ok=True)
    return asset_dir


def store_product_image(file_bytes: bytes) -> StoredProductAsset:
    encoded = sanitize_product_image(file_bytes)
    digest = hashlib.sha256(encoded).hexdigest()
    asset_dir = _asset_directory()
    target = asset_dir / f"{digest}.webp"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ProductAssetError("image_required")
        return StoredProductAsset(
            url=f"{settings.PUBLIC_ASSET_BASE_URL.rstrip('/')}/product-assets/{target.name}",
            path=target,
            created=False,
        )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=asset_dir,
        prefix=".asset-",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    created = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
            created = True
        except FileExistsError:
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ProductAssetError("image_required")
    finally:
        temporary.unlink(missing_ok=True)

    return StoredProductAsset(
        url=f"{settings.PUBLIC_ASSET_BASE_URL.rstrip('/')}/product-assets/{target.name}",
        path=target,
        created=created,
    )


def discard_new_asset(asset: StoredProductAsset) -> None:
    if asset.created:
        asset.path.unlink(missing_ok=True)


def owned_product_asset_path(asset_url: str | None) -> Path | None:
    if not asset_url:
        return None
    prefix = f"{settings.PUBLIC_ASSET_BASE_URL.rstrip('/')}/product-assets/"
    if not asset_url.startswith(prefix):
        return None
    name = asset_url.removeprefix(prefix)
    if not _OWNED_ASSET_NAME.fullmatch(name):
        return None
    asset_dir = _asset_directory()
    candidate = (asset_dir / name).resolve()
    if candidate.parent != asset_dir:
        return None
    return candidate


def delete_owned_product_asset(asset_url: str | None) -> bool:
    path = owned_product_asset_path(asset_url)
    if path is None or not path.exists():
        return False
    path.unlink()
    return True
