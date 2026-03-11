from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    schedule_hours_local: list[int] = Field(default_factory=lambda: [7, 12, 17])
    queue_name: str = "assistant"
    log_level: str = "INFO"


class FiltersConfig(BaseModel):
    email_noise_senders: list[str] = Field(default_factory=list)
    email_noise_subject_keywords: list[str] = Field(default_factory=list)


class RedactionConfig(BaseModel):
    enabled: bool = True
    custom_sensitive_terms: list[str] = Field(default_factory=list)


class DeliveryConfig(BaseModel):
    digest_subject_prefix: str = "AI Ops Digest"
    outbox_dir: str = "data/outbox"


class SourceToggleConfig(BaseModel):
    enabled: bool = True


class SourcesConfig(BaseModel):
    gmail: SourceToggleConfig = Field(default_factory=SourceToggleConfig)
    github: SourceToggleConfig = Field(default_factory=SourceToggleConfig)
    calendar: SourceToggleConfig = Field(default_factory=SourceToggleConfig)
    hedy: SourceToggleConfig = Field(default_factory=SourceToggleConfig)


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    redaction: RedactionConfig = Field(default_factory=RedactionConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)

    redis_url: str = "redis://localhost:6379/0"
    database_path: str = "data/assistant.db"
    local_timezone: str = "America/New_York"
    checkpoint_overlap_minutes: int = 10
    lookback_days: int = 30
    gmail_page_size: int = 100
    gmail_max_pages: int = 10
    gmail_pending_thread_limit: int = 200
    gmail_thread_context_max_messages: int = 0

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    llm_monthly_budget_usd: float = 20.0

    delivery_email_enabled: bool = False
    delivery_sms_enabled: bool = False

    digest_email_to: str = ""
    digest_email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    twilio_to: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token_work: str = ""
    google_refresh_token_personal: str = ""
    google_calendar_ids: list[str] = Field(default_factory=list)

    github_token: str = ""
    github_org: str = ""

    hedy_api_base_url: str = ""
    hedy_api_key: str = ""

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    seed_mock_data_if_empty: bool = True
    encryption_key_path: str = "data/secret.key"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_runtime_path(path_value: str, project_root: Path) -> str:
    path = Path(path_value)
    if path.is_absolute():
        # Support local runs even when .env uses container paths like /app/data/...
        if path_value.startswith("/app/") and not Path("/app").exists():
            return str(project_root / path_value.removeprefix("/app/"))
        return path_value
    return str(project_root / path)


def _resolve_redis_url(redis_url: str) -> str:
    parsed = urlparse(redis_url)
    if parsed.hostname != "redis":
        return redis_url
    if Path("/app").exists():
        return redis_url
    netloc = "127.0.0.1"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    yaml_data = _load_yaml(root / "config" / "settings.yaml")

    base = Settings(**yaml_data)

    database_path = _resolve_runtime_path(
        os.getenv("DATABASE_PATH", base.database_path),
        root,
    )
    encryption_key_path = _resolve_runtime_path(
        os.getenv("ENCRYPTION_KEY_PATH", base.encryption_key_path),
        root,
    )
    outbox_dir = _resolve_runtime_path(base.delivery.outbox_dir, root)

    return base.model_copy(
        update={
            "redis_url": _resolve_redis_url(os.getenv("REDIS_URL", base.redis_url)),
            "database_path": database_path,
            "local_timezone": os.getenv("LOCAL_TIMEZONE", base.local_timezone),
            "checkpoint_overlap_minutes": int(
                os.getenv("CHECKPOINT_OVERLAP_MINUTES", str(base.checkpoint_overlap_minutes))
            ),
            "lookback_days": int(os.getenv("LOOKBACK_DAYS", str(base.lookback_days))),
            "gmail_page_size": int(os.getenv("GMAIL_PAGE_SIZE", str(base.gmail_page_size))),
            "gmail_max_pages": int(os.getenv("GMAIL_MAX_PAGES", str(base.gmail_max_pages))),
            "gmail_pending_thread_limit": int(
                os.getenv("GMAIL_PENDING_THREAD_LIMIT", str(base.gmail_pending_thread_limit))
            ),
            "gmail_thread_context_max_messages": int(
                os.getenv(
                    "GMAIL_THREAD_CONTEXT_MAX_MESSAGES",
                    str(base.gmail_thread_context_max_messages),
                )
            ),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", base.anthropic_api_key),
            "anthropic_model": os.getenv("ANTHROPIC_MODEL", base.anthropic_model),
            "llm_monthly_budget_usd": float(
                os.getenv("LLM_MONTHLY_BUDGET_USD", str(base.llm_monthly_budget_usd))
            ),
            "delivery_email_enabled": _to_bool(
                os.getenv("DELIVERY_EMAIL_ENABLED"), base.delivery_email_enabled
            ),
            "delivery_sms_enabled": _to_bool(
                os.getenv("DELIVERY_SMS_ENABLED"), base.delivery_sms_enabled
            ),
            "digest_email_to": os.getenv("DIGEST_EMAIL_TO", base.digest_email_to),
            "digest_email_from": os.getenv("DIGEST_EMAIL_FROM", base.digest_email_from),
            "smtp_host": os.getenv("SMTP_HOST", base.smtp_host),
            "smtp_port": int(os.getenv("SMTP_PORT", str(base.smtp_port))),
            "smtp_username": os.getenv("SMTP_USERNAME", base.smtp_username),
            "smtp_password": os.getenv("SMTP_PASSWORD", base.smtp_password),
            "smtp_use_tls": _to_bool(os.getenv("SMTP_USE_TLS"), base.smtp_use_tls),
            "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", base.twilio_account_sid),
            "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", base.twilio_auth_token),
            "twilio_from": os.getenv("TWILIO_FROM", base.twilio_from),
            "twilio_to": os.getenv("TWILIO_TO", base.twilio_to),
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID", base.google_client_id),
            "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", base.google_client_secret),
            "google_refresh_token_work": os.getenv(
                "GOOGLE_REFRESH_TOKEN_WORK", base.google_refresh_token_work
            ),
            "google_refresh_token_personal": os.getenv(
                "GOOGLE_REFRESH_TOKEN_PERSONAL", base.google_refresh_token_personal
            ),
            "google_calendar_ids": _split_csv(
                os.getenv("GOOGLE_CALENDAR_IDS", ",".join(base.google_calendar_ids))
            ),
            "github_token": os.getenv("GITHUB_TOKEN", base.github_token),
            "github_org": os.getenv("GITHUB_ORG", base.github_org),
            "hedy_api_base_url": os.getenv("HEDY_API_BASE_URL", base.hedy_api_base_url),
            "hedy_api_key": os.getenv("HEDY_API_KEY", base.hedy_api_key),
            "supabase_url": os.getenv("SUPABASE_URL", base.supabase_url),
            "supabase_service_role_key": os.getenv(
                "SUPABASE_SERVICE_ROLE_KEY", base.supabase_service_role_key
            ),
            "seed_mock_data_if_empty": _to_bool(
                os.getenv("SEED_MOCK_DATA_IF_EMPTY"), base.seed_mock_data_if_empty
            ),
            "encryption_key_path": encryption_key_path,
            "delivery": base.delivery.model_copy(update={"outbox_dir": outbox_dir}),
        }
    )
