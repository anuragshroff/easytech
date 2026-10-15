"""Request/response schemas for the local wallet and billing settings."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WalletSettingsResponse(BaseModel):
    rate_cents_per_minute: int
    minimum_balance_cents: int
    enforce_pre_call_balance: bool
    auto_recharge_enabled: bool
    auto_recharge_threshold_cents: int
    auto_recharge_amount_cents: int


class PaymentLinkResponse(BaseModel):
    label: str
    amount_cents: int
    url: str


class WalletTotalsResponse(BaseModel):
    call_count: int
    total_duration_seconds: int
    total_amount_cents: int


class WalletOverviewResponse(BaseModel):
    balance_cents: int
    currency: str = "usd"
    settings: WalletSettingsResponse
    payment_links: List[PaymentLinkResponse] = []
    totals: WalletTotalsResponse


class WalletTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_cents: int
    currency: str
    kind: str
    source: str
    description: Optional[str] = None
    workflow_run_id: Optional[int] = None
    created_at: datetime


class WalletTransactionsResponse(BaseModel):
    transactions: List[WalletTransactionResponse]


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_run_id: int
    duration_seconds: int
    rate_cents_per_minute: int
    amount_cents: int
    created_at: datetime


class UsageRecordsResponse(BaseModel):
    usage_records: List[UsageRecordResponse]


class UpdateWalletSettingsRequest(BaseModel):
    """Org-scoped self-service settings (auto-recharge). Pricing is admin-only."""

    auto_recharge_enabled: Optional[bool] = None
    auto_recharge_threshold_cents: Optional[int] = Field(default=None, ge=0)
    auto_recharge_amount_cents: Optional[int] = Field(default=None, ge=0)
