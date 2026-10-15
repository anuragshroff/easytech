"""DID search + purchase for the carrier-backed providers."""

from unittest.mock import AsyncMock, patch

import pytest

from api.services.telephony.base import (
    ProviderPhoneNumberLookupError,
    ProviderSyncResult,
)
from api.services.telephony.providers.telnyx.provider import TelnyxProvider
from api.services.telephony.providers.twilio.provider import TwilioProvider


class _StubResponse:
    def __init__(self, status: int, *, data=None, body: str = ""):
        self.status = status
        self._data = data
        self._body = body

    async def json(self):
        return self._data

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _StubSession:
    def __init__(self, responses: list[_StubResponse]):
        self.responses = responses
        self.requests: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)

    def post(self, url: str, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _twilio() -> TwilioProvider:
    return TwilioProvider(
        {"account_sid": "AC123", "auth_token": "token", "from_numbers": []}
    )


def _telnyx() -> TelnyxProvider:
    return TelnyxProvider({"api_key": "KEY", "connection_id": "conn"})


@pytest.mark.asyncio
async def test_twilio_search_parses_inventory_and_passes_filters():
    provider = _twilio()
    session = _StubSession(
        [
            _StubResponse(
                200,
                data={
                    "available_phone_numbers": [
                        {
                            "phone_number": "+15551230001",
                            "friendly_name": "(555) 123-0001",
                            "locality": "San Francisco",
                            "region": "CA",
                            "iso_country": "US",
                            "capabilities": {"voice": True, "sms": True},
                        }
                    ]
                },
            )
        ]
    )

    with patch(
        "api.services.telephony.providers.twilio.provider.aiohttp.ClientSession",
        return_value=session,
    ):
        numbers = await provider.search_available_numbers(
            country_code="us", area_code="555", contains="123", limit=5
        )

    assert len(numbers) == 1
    assert numbers[0].phone_number == "+15551230001"
    assert numbers[0].locality == "San Francisco"
    assert numbers[0].capabilities == {"voice": True, "sms": True}
    url, kwargs = session.requests[0]
    assert url.endswith("/AvailablePhoneNumbers/US/Local.json")
    assert kwargs["params"] == {"PageSize": 5, "AreaCode": "555", "Contains": "123"}


@pytest.mark.asyncio
async def test_twilio_search_requires_credentials():
    provider = TwilioProvider({"from_numbers": []})
    with pytest.raises(ProviderPhoneNumberLookupError):
        await provider.search_available_numbers()


@pytest.mark.asyncio
async def test_twilio_provision_buys_unowned_number():
    provider = _twilio()
    provider._lookup_incoming_number_sid = AsyncMock(return_value=None)
    session = _StubSession([_StubResponse(201, data={"sid": "PN1"})])

    with patch(
        "api.services.telephony.providers.twilio.provider.aiohttp.ClientSession",
        return_value=session,
    ):
        result = await provider.provision_phone_number("+15551230002")

    assert result is not None and result.ok
    assert session.requests[0][1]["data"] == {"PhoneNumber": "+15551230002"}
    assert session.requests[0][0].endswith("/IncomingPhoneNumbers.json")


@pytest.mark.asyncio
async def test_twilio_provision_is_idempotent_when_owned():
    provider = _twilio()
    provider._lookup_incoming_number_sid = AsyncMock(return_value="PN1")

    with patch(
        "api.services.telephony.providers.twilio.provider.aiohttp.ClientSession"
    ) as session_cls:
        result = await provider.provision_phone_number("+15551230002")

    assert result is not None and result.ok
    session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_telnyx_search_parses_inventory():
    provider = _telnyx()
    session = _StubSession(
        [
            _StubResponse(
                200,
                data={
                    "data": [
                        {
                            "phone_number": "+15551230001",
                            "features": {"voice": True},
                            "region_information": {
                                "region_name": "California",
                                "country_code": "US",
                            },
                            "cost_information": {"monthly_cost": "1.00"},
                        }
                    ]
                },
            )
        ]
    )

    with patch(
        "api.services.telephony.providers.telnyx.provider.aiohttp.ClientSession",
        return_value=session,
    ):
        numbers = await provider.search_available_numbers(
            country_code="US", area_code="555", limit=5
        )

    assert len(numbers) == 1
    assert numbers[0].phone_number == "+15551230001"
    assert numbers[0].region == "California"
    assert numbers[0].price == "1.00"
    assert session.requests[0][1]["params"]["filter[national_destination_code]"] == "555"


@pytest.mark.asyncio
async def test_telnyx_provision_orders_unowned_number():
    provider = _telnyx()
    provider.validate_phone_number = AsyncMock(
        return_value=ProviderSyncResult(ok=False, message="not owned")
    )
    session = _StubSession([_StubResponse(201, data={"data": {"id": "order1"}})])

    with patch(
        "api.services.telephony.providers.telnyx.provider.aiohttp.ClientSession",
        return_value=session,
    ):
        result = await provider.provision_phone_number("+15551230002")

    assert result is not None and result.ok
    url, kwargs = session.requests[0]
    assert url.endswith("/number_orders")
    assert kwargs["json"] == {"phone_numbers": [{"phone_number": "+15551230002"}]}


@pytest.mark.asyncio
async def test_telnyx_provision_is_idempotent_when_owned():
    provider = _telnyx()
    provider.validate_phone_number = AsyncMock(return_value=ProviderSyncResult(ok=True))

    with patch(
        "api.services.telephony.providers.telnyx.provider.aiohttp.ClientSession"
    ) as session_cls:
        result = await provider.provision_phone_number("+15551230002")

    assert result is not None and result.ok
    session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_search_route_maps_provider_results():
    from types import SimpleNamespace

    from api.routes.organization import search_available_phone_numbers
    from api.services.telephony.base import AvailablePhoneNumber

    provider = SimpleNamespace(
        search_available_numbers=AsyncMock(
            return_value=[
                AvailablePhoneNumber(
                    phone_number="+15551230001", locality="SF", capabilities={"voice": True}
                )
            ]
        )
    )
    user = SimpleNamespace(selected_organization_id=1)

    with (
        patch(
            "api.routes.organization._ensure_config_belongs_to_org",
            new_callable=AsyncMock,
        ),
        patch(
            "api.routes.organization.get_telephony_provider_by_id",
            new_callable=AsyncMock,
            return_value=provider,
        ),
    ):
        response = await search_available_phone_numbers(
            config_id=3, country_code="US", area_code=None, contains=None, limit=20, user=user
        )

    assert response.numbers[0].phone_number == "+15551230001"
    assert response.numbers[0].capabilities == {"voice": True}
    provider.search_available_numbers.assert_awaited_once_with(
        country_code="US", area_code=None, contains=None, limit=20
    )


@pytest.mark.asyncio
async def test_search_route_rejects_unsupported_provider():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from api.routes.organization import search_available_phone_numbers

    provider = SimpleNamespace(
        search_available_numbers=AsyncMock(side_effect=NotImplementedError("nope"))
    )
    user = SimpleNamespace(selected_organization_id=1)

    with (
        patch(
            "api.routes.organization._ensure_config_belongs_to_org",
            new_callable=AsyncMock,
        ),
        patch(
            "api.routes.organization.get_telephony_provider_by_id",
            new_callable=AsyncMock,
            return_value=provider,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await search_available_phone_numbers(
                config_id=3, country_code="US", area_code=None, contains=None, limit=20, user=user
            )

    assert exc_info.value.status_code == 400

