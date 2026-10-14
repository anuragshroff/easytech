import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.constants import (
    APP_VERSION,
    AUTH_PROVIDER,
    BACKEND_API_ENDPOINT,
    DEPLOYMENT_MODE,
    ENABLE_ARI_STASIS,
    ENABLE_CALL_RECORDING_UPLOAD,
    ENABLE_PROMETHEUS_METRICS,
    ENABLE_SIGNUP,
    ENABLE_TELEMETRY,
    ENVIRONMENT,
    FORCE_TURN_RELAY,
    LOG_LEVEL,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECURE,
    TELEPHONY_WS_TOKEN_ENFORCE,
    UI_APP_URL,
)
from api.db import db_client
from api.db.models import UserModel
from api.services.auth.depends import get_superuser
from api.services.auth.stack_auth import (
    StackAuthSessionError,
    StackAuthUserSearchError,
    stackauth,
)

router = APIRouter(prefix="/superuser", tags=["superuser"])


class ImpersonateRequest(BaseModel):
    """Request payload for superadmin impersonation.

    ``provider_user_id``, ``user_id``, or ``email`` may be supplied. If more
    than one is provided, ``provider_user_id`` takes precedence, followed by
    ``user_id`` and then ``email``.
    """

    provider_user_id: str | None = None
    user_id: int | None = None
    email: str | None = None


class ImpersonateResponse(BaseModel):
    refresh_token: str
    access_token: str


class SuperuserWorkflowRunResponse(BaseModel):
    id: int
    name: str
    workflow_id: int
    workflow_name: Optional[str]
    user_id: Optional[int]
    organization_id: Optional[int]
    organization_name: Optional[str]
    mode: str
    is_completed: bool
    recording_url: Optional[str]
    transcript_url: Optional[str]
    usage_info: Optional[dict]
    cost_info: Optional[dict]
    initial_context: Optional[dict]
    gathered_context: Optional[dict]
    created_at: datetime


class SuperuserWorkflowRunsListResponse(BaseModel):
    workflow_runs: List[SuperuserWorkflowRunResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int


class SuperuserStatsResponse(BaseModel):
    total_users: int
    total_organizations: int
    total_runs: int
    completed_runs: int
    active_runs: int
    runs_today: int


class SuperuserUserResponse(BaseModel):
    id: int
    email: Optional[str]
    provider_id: str
    is_superuser: bool
    is_active: bool = True
    organization_id: Optional[int]
    created_at: Optional[datetime]


class SuperuserUsersListResponse(BaseModel):
    users: List[SuperuserUserResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int


class SuperuserOrganizationResponse(BaseModel):
    id: int
    provider_id: str
    created_at: Optional[datetime]
    user_count: int
    run_count: int


class SuperuserOrganizationsListResponse(BaseModel):
    organizations: List[SuperuserOrganizationResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int


class ToggleSuperuserRequest(BaseModel):
    is_superuser: bool


class ToggleActiveRequest(BaseModel):
    is_active: bool


class SuperuserWorkflowSummary(BaseModel):
    id: int
    name: Optional[str]
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    run_count: int = 0


class SuperuserRunSummary(BaseModel):
    id: int
    name: str
    workflow_id: int
    workflow_name: Optional[str] = None
    mode: str
    is_completed: bool
    recording_url: Optional[str] = None
    transcript_url: Optional[str] = None
    created_at: datetime


class SuperuserOrganizationDetail(BaseModel):
    id: int
    provider_id: str
    created_at: Optional[datetime] = None
    price_per_second_usd: Optional[float] = None
    user_count: int
    run_count: int
    workflow_count: int


class SuperuserOrganizationMembersResponse(BaseModel):
    users: List[SuperuserUserResponse]


class SuperuserOrganizationWorkflowsResponse(BaseModel):
    workflows: List[SuperuserWorkflowSummary]


class SuperuserOrganizationRunsListResponse(BaseModel):
    runs: List[SuperuserRunSummary]
    total_count: int
    page: int
    limit: int
    total_pages: int


class PlatformUsageOrg(BaseModel):
    organization_id: int
    provider_id: str
    price_per_second_usd: Optional[float]
    call_count: int
    total_seconds: float
    total_minutes: float
    cost_usd: float


class PlatformUsageTotals(BaseModel):
    call_count: int
    total_seconds: float
    total_minutes: float
    cost_usd: float


class PlatformUsageOverviewResponse(BaseModel):
    period_start: str
    period_end: str
    organizations: List[PlatformUsageOrg]
    totals: PlatformUsageTotals


class PlatformSettingsResponse(BaseModel):
    version: str
    deployment_mode: str
    auth_provider: str
    signup_enabled: bool
    turn_enabled: bool
    force_turn_relay: bool
    backend_api_endpoint: str
    ui_app_url: str
    enable_telemetry: bool
    enable_prometheus_metrics: bool
    enable_ari_stasis: bool
    log_level: str
    minio_endpoint: str
    minio_bucket: str
    minio_secure: bool
    call_recording_upload: bool
    telephony_ws_enforce: bool
    environment: str


@router.post("/impersonate")
async def impersonate(
    request: ImpersonateRequest, user: UserModel = Depends(get_superuser)
) -> ImpersonateResponse:
    """Impersonate a user as a super-admin.
    Internally, Stack Auth requires the **provider user ID** (a UUID-ish string)
    to create an impersonation session.
    """

    provider_user_id = (
        request.provider_user_id.strip() if request.provider_user_id else None
    ) or None
    email = request.email.strip().lower() if request.email else None

    # ------------------------------------------------------------------
    # Fallback: resolve provider_user_id from internal ``user_id`` or email.
    # ------------------------------------------------------------------
    if provider_user_id is None:
        if request.user_id is not None:
            db_user = await db_client.get_user_by_id(request.user_id)

            if db_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with ID {request.user_id} not found.",
                )

            provider_user_id = db_user.provider_id
        elif email:
            db_user = await db_client.get_user_by_email(email)

            if db_user is not None:
                provider_user_id = db_user.provider_id
            else:
                try:
                    stack_users = await stackauth.find_users_by_email(email)
                except StackAuthUserSearchError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to search Stack Auth users.",
                    ) from exc

                if len(stack_users) == 1 and isinstance(stack_users[0].get("id"), str):
                    provider_user_id = stack_users[0]["id"]
                elif len(stack_users) > 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Multiple Stack Auth users matched that email.",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User with email {email} not found.",
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "One of 'provider_user_id', 'user_id', or 'email' must be provided."
                ),
            )

    # ------------------------------------------------------------------
    # Call Stack Auth to create the impersonation session
    # ------------------------------------------------------------------
    try:
        session = await stackauth.impersonate(provider_user_id)
    except StackAuthSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Stack Auth impersonation session.",
        ) from exc

    if (
        not isinstance(session, dict)
        or "refresh_token" not in session
        or "access_token" not in session
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Stack Auth impersonation session.",
        )

    return ImpersonateResponse(
        refresh_token=session["refresh_token"],
        access_token=session["access_token"],
    )


@router.get("/workflow-runs")
async def get_workflow_runs(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(50, ge=1, le=100, description="Number of items per page"),
    filters: Optional[str] = Query(None, description="JSON-encoded filter criteria"),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (e.g., 'duration', 'created_at')"
    ),
    sort_order: Optional[str] = Query(
        "desc", description="Sort order ('asc' or 'desc')"
    ),
    user: UserModel = Depends(get_superuser),
) -> SuperuserWorkflowRunsListResponse:
    """
    Get paginated list of all workflow runs with organization information.
    Requires superuser privileges.

    Filters should be provided as a JSON-encoded array of filter criteria.
    Example: [{"field": "id", "type": "number", "value": {"value": 680}}]
    """
    offset = (page - 1) * limit

    # Parse filters if provided
    filter_criteria = None
    if filters:
        try:
            filter_criteria = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid filter format")

    # Validate sort_order
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    workflow_runs, total_count = await db_client.get_workflow_runs_for_superadmin(
        limit=limit,
        offset=offset,
        filters=filter_criteria,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = (total_count + limit - 1) // limit  # Ceiling division

    return SuperuserWorkflowRunsListResponse(
        workflow_runs=[SuperuserWorkflowRunResponse(**run) for run in workflow_runs],
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/stats")
async def get_stats(
    user: UserModel = Depends(get_superuser),
) -> SuperuserStatsResponse:
    """Platform-wide counters for the admin dashboard."""
    stats = await db_client.get_superadmin_stats()
    return SuperuserStatsResponse(**stats)


@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, description="Partial email match"),
    user: UserModel = Depends(get_superuser),
) -> SuperuserUsersListResponse:
    """Paginated list of all users with their selected organization."""
    offset = (page - 1) * limit
    users, total_count = await db_client.get_users_for_superadmin(
        limit=limit,
        offset=offset,
        search=search,
    )
    total_pages = (total_count + limit - 1) // limit
    return SuperuserUsersListResponse(
        users=[SuperuserUserResponse(**u) for u in users],
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/organizations")
async def get_organizations(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, description="Partial provider_id match"),
    user: UserModel = Depends(get_superuser),
) -> SuperuserOrganizationsListResponse:
    """Paginated list of all organizations with member and run counts."""
    offset = (page - 1) * limit
    organizations, total_count = await db_client.get_organizations_for_superadmin(
        limit=limit,
        offset=offset,
        search=search,
    )
    total_pages = (total_count + limit - 1) // limit
    return SuperuserOrganizationsListResponse(
        organizations=[
            SuperuserOrganizationResponse(**o) for o in organizations
        ],
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.post("/users/{user_id}/superuser")
async def set_user_superuser(
    user_id: int,
    body: ToggleSuperuserRequest,
    user: UserModel = Depends(get_superuser),
) -> dict:
    if user_id == user.id:
        raise HTTPException(
            status_code=400, detail="Cannot change superuser status of yourself"
        )
    result = await db_client.set_superuser(user_id, body.is_superuser)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "is_superuser": result}


@router.post("/users/{user_id}/active")
async def set_user_active(
    user_id: int,
    body: ToggleActiveRequest,
    user: UserModel = Depends(get_superuser),
) -> dict:
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    result = await db_client.set_user_active(user_id, body.is_active)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "is_active": result}


@router.get("/organizations/{org_id}", response_model=SuperuserOrganizationDetail)
async def get_organization_detail(
    org_id: int, user: UserModel = Depends(get_superuser)
) -> SuperuserOrganizationDetail:
    detail = await db_client.get_organization_detail_superadmin(org_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return SuperuserOrganizationDetail(**detail)


@router.get(
    "/organizations/{org_id}/members",
    response_model=SuperuserOrganizationMembersResponse,
)
async def get_organization_members(
    org_id: int, user: UserModel = Depends(get_superuser)
) -> SuperuserOrganizationMembersResponse:
    members = await db_client.get_organization_users(org_id)
    users = [
        SuperuserUserResponse(
            id=m.id,
            email=m.email,
            provider_id=m.provider_id,
            is_superuser=m.is_superuser,
            is_active=getattr(m, "is_active", True),
            organization_id=m.selected_organization_id,
            created_at=m.created_at,
        )
        for m in members
    ]
    return SuperuserOrganizationMembersResponse(users=users)


@router.get(
    "/organizations/{org_id}/workflows",
    response_model=SuperuserOrganizationWorkflowsResponse,
)
async def get_organization_workflows(
    org_id: int, user: UserModel = Depends(get_superuser)
) -> SuperuserOrganizationWorkflowsResponse:
    workflows = await db_client.get_organization_workflows_superadmin(org_id)
    return SuperuserOrganizationWorkflowsResponse(
        workflows=[SuperuserWorkflowSummary(**w) for w in workflows]
    )


@router.get(
    "/organizations/{org_id}/runs",
    response_model=SuperuserOrganizationRunsListResponse,
)
async def get_organization_runs(
    org_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user: UserModel = Depends(get_superuser),
) -> SuperuserOrganizationRunsListResponse:
    offset = (page - 1) * limit
    runs, total_count = await db_client.get_organization_runs_superadmin(
        org_id, limit=limit, offset=offset
    )
    total_pages = (total_count + limit - 1) // limit
    return SuperuserOrganizationRunsListResponse(
        runs=[SuperuserRunSummary(**r) for r in runs],
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/usage", response_model=PlatformUsageOverviewResponse)
async def get_platform_usage(
    user: UserModel = Depends(get_superuser),
) -> PlatformUsageOverviewResponse:
    overview = await db_client.get_usage_overview()
    return PlatformUsageOverviewResponse(**overview)


@router.get("/settings", response_model=PlatformSettingsResponse)
async def get_platform_settings(
    user: UserModel = Depends(get_superuser),
) -> PlatformSettingsResponse:
    return PlatformSettingsResponse(
        version=APP_VERSION,
        deployment_mode=DEPLOYMENT_MODE,
        auth_provider=AUTH_PROVIDER,
        signup_enabled=ENABLE_SIGNUP,
        turn_enabled=ENABLE_ARI_STASIS is not True,  # just keep consistent with health
        force_turn_relay=FORCE_TURN_RELAY,
        backend_api_endpoint=BACKEND_API_ENDPOINT,
        ui_app_url=UI_APP_URL,
        enable_telemetry=ENABLE_TELEMETRY,
        enable_prometheus_metrics=ENABLE_PROMETHEUS_METRICS,
        enable_ari_stasis=ENABLE_ARI_STASIS,
        log_level=LOG_LEVEL,
        minio_endpoint=MINIO_ENDPOINT,
        minio_bucket=MINIO_BUCKET,
        minio_secure=MINIO_SECURE,
        call_recording_upload=ENABLE_CALL_RECORDING_UPLOAD,
        telephony_ws_enforce=TELEPHONY_WS_TOKEN_ENFORCE,
        environment=ENVIRONMENT,
    )
