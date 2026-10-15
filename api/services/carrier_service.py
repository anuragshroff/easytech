"""Master-carrier account model.

OSS is bring-your-own-carrier: each organization stores its own Twilio/Telnyx
credentials on a telephony configuration, and DID search/purchase runs against
those credentials. A *hosted* deployment can instead own a single master
carrier account and provision numbers centrally, then attach them to tenants.

This module is the seam for that second mode. It is strictly opt-in and
env-driven: when the master credentials for a provider are absent,
``build_master_provider`` returns None and callers keep using the org's own
configuration — the default OSS path — with no other change.

ponytail: this exposes the master provider (search + purchase) only. Fully
centralised provisioning — buying on the master account *and* binding the
inbound webhook on the master account so the number's runtime config also
lives centrally — is the follow-up; today an org that buys through the master
account still owns the number row locally. Wire the numbering/webhook sync
through here when a hosted deployment actually enables this.
"""

import os
from typing import Any, Dict, Optional

from loguru import logger

from api.services.telephony import registry
from api.services.telephony.base import TelephonyProvider

# Provider name -> the env vars holding that provider's master account
# credentials. Values mirror the credential shape each provider's
# ``config_loader`` expects.
MASTER_CARRIER_ENV: Dict[str, Dict[str, str]] = {
    "twilio": {
        "account_sid": "MASTER_TWILIO_ACCOUNT_SID",
        "auth_token": "MASTER_TWILIO_AUTH_TOKEN",
    },
    "telnyx": {
        "api_key": "MASTER_TELNYX_API_KEY",
        "connection_id": "MASTER_TELNYX_CONNECTION_ID",
    },
}


def get_master_carrier_credentials(provider_name: str) -> Optional[Dict[str, Any]]:
    """Raw master credentials for ``provider_name``, or None if not configured.

    Returns None unless *every* env var for the provider is set — a partial
    config is treated as "not configured" rather than yielding a provider that
    would fail later with a confusing auth error.
    """
    env_map = MASTER_CARRIER_ENV.get(provider_name)
    if not env_map:
        return None
    values = {key: os.getenv(env) for key, env in env_map.items()}
    if not all(values.values()):
        return None
    return values


def is_master_carrier_configured(provider_name: str) -> bool:
    return get_master_carrier_credentials(provider_name) is not None


def build_master_provider(provider_name: str) -> Optional[TelephonyProvider]:
    """Build a provider instance backed by the master account, or None.

    The instance is for carrier operations (search/purchase) — it carries no
    org context and no caller-ID pool, so it must not be handed to the call
    path. Use it only where a route has decided to serve a request from the
    master account.
    """
    credentials = get_master_carrier_credentials(provider_name)
    if credentials is None:
        return None

    spec = registry.get_optional(provider_name)
    if spec is None:
        logger.warning(
            f"Master carrier configured for unknown provider '{provider_name}'"
        )
        return None

    # config_loader is a pure dict reshape (enforced by the registry contract).
    return spec.provider_cls(spec.config_loader(credentials))


def _self_check() -> None:
    """Runnable check: partial/unset master config resolves to None, not a
    half-built provider."""
    for env in ("MASTER_TWILIO_ACCOUNT_SID", "MASTER_TWILIO_AUTH_TOKEN"):
        os.environ.pop(env, None)
    assert get_master_carrier_credentials("twilio") is None
    assert build_master_provider("twilio") is None

    os.environ["MASTER_TWILIO_ACCOUNT_SID"] = "AC_test"
    assert get_master_carrier_credentials("twilio") is None, "partial must be None"
    os.environ["MASTER_TWILIO_AUTH_TOKEN"] = "tok"
    creds = get_master_carrier_credentials("twilio")
    assert creds == {"account_sid": "AC_test", "auth_token": "tok"}
    assert get_master_carrier_credentials("unknown") is None
    print("carrier_service self-check ok")


if __name__ == "__main__":
    _self_check()
