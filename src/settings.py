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


class DraftRoutingConfig(BaseModel):
    email_patterns: list[str] = Field(default_factory=list)
    is_default: bool = False


class WorkspaceConfig(BaseModel):
    slug: str = ""
    name: str = ""
    description: str = ""
    sources: list[str] = Field(default_factory=list)
    sort_order: int = 0
    draft_routing: DraftRoutingConfig = Field(default_factory=DraftRoutingConfig)


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

    # Workspace configuration (loaded from config/workspaces.yaml)
    workspaces: dict[str, WorkspaceConfig] = Field(default_factory=dict)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env(key: str, default: str = "") -> str:
    """Get env var, treating empty strings as the default."""
    value = os.getenv(key)
    return value if value else default


def _env_int(key: str, default: int) -> int:
    """Get env var as int."""
    value = os.getenv(key)
    return int(value) if value else default


def _env_float(key: str, default: float) -> float:
    """Get env var as float."""
    value = os.getenv(key)
    return float(value) if value else default


def _env_bool(key: str, default: bool) -> bool:
    """Get env var as bool."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: list[str] | None = None) -> list[str]:
    """Get env var as comma-separated list."""
    value = os.getenv(key)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_path(path_value: str, project_root: Path) -> str:
    """Resolve path relative to project root, handling Docker paths."""
    path = Path(path_value)
    if path.is_absolute():
        if path_value.startswith("/app/") and not Path("/app").exists():
            return str(project_root / path_value.removeprefix("/app/"))
        return path_value
    return str(project_root / path)


def _resolve_redis_url(redis_url: str) -> str:
    """Convert Docker redis hostname to localhost for local dev."""
    parsed = urlparse(redis_url)
    if parsed.hostname != "redis":
        return redis_url
    if Path("/app").exists():
        return redis_url
    netloc = "127.0.0.1"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def _load_workspaces(root: Path) -> dict[str, WorkspaceConfig]:
    """Load workspace configuration from config/workspaces.yaml."""
    data = _load_yaml(root / "config" / "workspaces.yaml")
    workspaces: dict[str, WorkspaceConfig] = {}

    for slug, config in data.get("workspaces", {}).items():
        draft_routing_data = config.get("draft_routing", {})
        workspaces[slug] = WorkspaceConfig(
            slug=slug,
            name=config.get("name", slug),
            description=config.get("description", ""),
            sources=config.get("sources", []),
            sort_order=config.get("sort_order", 0),
            draft_routing=DraftRoutingConfig(
                email_patterns=draft_routing_data.get("email_patterns", []),
                is_default=draft_routing_data.get("is_default", False),
            ),
        )

    return workspaces


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    yaml_data = _load_yaml(root / "config" / "settings.yaml")
    workspaces = _load_workspaces(root)

    base = Settings(**yaml_data)

    # Build settings with env var overrides
    settings = base.model_copy(
        update={
            "redis_url": _resolve_redis_url(_env("REDIS_URL", base.redis_url)),
            "database_path": _resolve_path(_env("DATABASE_PATH", base.database_path), root),
            "local_timezone": _env("LOCAL_TIMEZONE", base.local_timezone),
            "checkpoint_overlap_minutes": _env_int("CHECKPOINT_OVERLAP_MINUTES", base.checkpoint_overlap_minutes),
            "lookback_days": _env_int("LOOKBACK_DAYS", base.lookback_days),
            "gmail_page_size": _env_int("GMAIL_PAGE_SIZE", base.gmail_page_size),
            "gmail_max_pages": _env_int("GMAIL_MAX_PAGES", base.gmail_max_pages),
            "gmail_pending_thread_limit": _env_int("GMAIL_PENDING_THREAD_LIMIT", base.gmail_pending_thread_limit),
            "gmail_thread_context_max_messages": _env_int("GMAIL_THREAD_CONTEXT_MAX_MESSAGES", base.gmail_thread_context_max_messages),
            "anthropic_api_key": _env("ANTHROPIC_API_KEY", base.anthropic_api_key),
            "anthropic_model": _env("ANTHROPIC_MODEL", base.anthropic_model),
            "llm_monthly_budget_usd": _env_float("LLM_MONTHLY_BUDGET_USD", base.llm_monthly_budget_usd),
            "delivery_email_enabled": _env_bool("DELIVERY_EMAIL_ENABLED", base.delivery_email_enabled),
            "delivery_sms_enabled": _env_bool("DELIVERY_SMS_ENABLED", base.delivery_sms_enabled),
            "digest_email_to": _env("DIGEST_EMAIL_TO", base.digest_email_to),
            "digest_email_from": _env("DIGEST_EMAIL_FROM", base.digest_email_from),
            "smtp_host": _env("SMTP_HOST", base.smtp_host),
            "smtp_port": _env_int("SMTP_PORT", base.smtp_port),
            "smtp_username": _env("SMTP_USERNAME", base.smtp_username),
            "smtp_password": _env("SMTP_PASSWORD", base.smtp_password),
            "smtp_use_tls": _env_bool("SMTP_USE_TLS", base.smtp_use_tls),
            "twilio_account_sid": _env("TWILIO_ACCOUNT_SID", base.twilio_account_sid),
            "twilio_auth_token": _env("TWILIO_AUTH_TOKEN", base.twilio_auth_token),
            "twilio_from": _env("TWILIO_FROM", base.twilio_from),
            "twilio_to": _env("TWILIO_TO", base.twilio_to),
            "google_client_id": _env("GOOGLE_CLIENT_ID", base.google_client_id),
            "google_client_secret": _env("GOOGLE_CLIENT_SECRET", base.google_client_secret),
            "google_refresh_token_work": _env("GOOGLE_REFRESH_TOKEN_WORK", base.google_refresh_token_work),
            "google_refresh_token_personal": _env("GOOGLE_REFRESH_TOKEN_PERSONAL", base.google_refresh_token_personal),
            "google_calendar_ids": _env_list("GOOGLE_CALENDAR_IDS", base.google_calendar_ids),
            "github_token": _env("GITHUB_TOKEN", base.github_token),
            "github_org": _env("GITHUB_ORG", base.github_org),
            "hedy_api_base_url": _env("HEDY_API_BASE_URL", base.hedy_api_base_url),
            "hedy_api_key": _env("HEDY_API_KEY", base.hedy_api_key),
            "supabase_url": _env("SUPABASE_URL", base.supabase_url),
            "supabase_service_role_key": _env("SUPABASE_SERVICE_ROLE_KEY", base.supabase_service_role_key),
            "seed_mock_data_if_empty": _env_bool("SEED_MOCK_DATA_IF_EMPTY", base.seed_mock_data_if_empty),
            "encryption_key_path": _resolve_path(_env("ENCRYPTION_KEY_PATH", base.encryption_key_path), root),
            "delivery": base.delivery.model_copy(
                update={"outbox_dir": _resolve_path(base.delivery.outbox_dir, root)}
            ),
            "workspaces": workspaces,
        }
    )

    return settings


def workspace_for_source(settings: Settings, source: str) -> str:
    """Get workspace slug for a source based on configuration."""
    for slug, workspace in settings.workspaces.items():
        if source in workspace.sources:
            return slug
    return "downer"  # Default fallback


def workspace_for_draft(settings: Settings, recipient: str) -> str:
    """Get workspace slug for a draft based on recipient email patterns."""
    recipient_lower = recipient.lower()
    default_workspace = "downer"

    for slug, workspace in settings.workspaces.items():
        if workspace.draft_routing.is_default:
            default_workspace = slug
            continue

        for pattern in workspace.draft_routing.email_patterns:
            if pattern.lower() in recipient_lower:
                return slug

    return default_workspace
