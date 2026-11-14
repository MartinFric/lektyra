"""Settings and keys, parsed once (ADR-001). Keys are SecretStr: they never print (ADR-005)."""

from pathlib import Path
from typing import Final

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_FILE: Final = Path.home() / ".secrets" / "lektyra.env"
MINIO_FILE: Final = Path.home() / ".secrets" / "lektyra-minio.env"  # shared with compose.yaml


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(SECRETS_FILE, MINIO_FILE), env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: SecretStr | None = None
    soniox_api_key: SecretStr | None = None
    hf_token: SecretStr | None = None
    database_url: str = "postgresql://lektyra@127.0.0.1:55432/lektyra"
    # Pictures (ADR-015): lektyra's own MinIO from compose.yaml
    minio_url: str = "http://127.0.0.1:59000"
    minio_root_user: SecretStr | None = None
    minio_root_password: SecretStr | None = None
    pictures_bucket: str = "lektyra-pictures"
    videos_bucket: str = "lektyra-videos"  # uploaded to play as live (ADR-016)
    data_dir: Path = Path("data")
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    ytdlp: str = "yt-dlp"
    reviewer: str = "martin"  # who names, rates and flags in the local UI (audit_log, ADR-009)


def load_settings() -> Settings:
    return Settings()
