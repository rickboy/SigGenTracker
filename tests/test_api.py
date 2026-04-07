"""Tests for the Sigenergy Cloud API client."""

from __future__ import annotations

import base64

import aiohttp
import pytest

from custom_components.sigenergy_cloud.api import (
    SigenCloudApiClient,
    SigenCloudApiError,
    SigenCloudAuthError,
    _encrypt_password,
)
from custom_components.sigenergy_cloud.const import (
    ENDPOINT_STATION_HOME,
    REGION_EU,
)

from .conftest import (
    SAMPLE_AUTH_RESPONSE,
    SAMPLE_CURRENT_MODE,
    SAMPLE_ENERGY_FLOW,
    SAMPLE_STATION,
    make_mock_response,
)

# ---------------------------------------------------------------------------
# _encrypt_password
# ---------------------------------------------------------------------------


class TestEncryptPassword:
    """Tests for the AES-CBC password encryption helper."""

    def test_returns_base64_string(self):
        result = _encrypt_password("testpassword")
        # Must be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_deterministic(self):
        """Same password always produces the same ciphertext."""
        a = _encrypt_password("hello123")
        b = _encrypt_password("hello123")
        assert a == b

    def test_different_passwords_differ(self):
        a = _encrypt_password("password1")
        b = _encrypt_password("password2")
        assert a != b

    def test_empty_password(self):
        """Empty string should still encrypt (PKCS7 pads to one block)."""
        result = _encrypt_password("")
        decoded = base64.b64decode(result)
        assert len(decoded) == 16  # one AES block


# ---------------------------------------------------------------------------
# SigenCloudApiClient — authentication
# ---------------------------------------------------------------------------


class TestAuthenticate:
    """Tests for SigenCloudApiClient.authenticate()."""

    @pytest.mark.asyncio
    async def test_successful_auth(self, mock_session):
        resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = resp

        client = SigenCloudApiClient(mock_session, "user@test.com", "pass123")
        await client.authenticate()

        assert client._access_token == "test-access-token-12345"
        assert client._refresh_token_value == "test-refresh-token-67890"
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_http_error(self, mock_session):
        resp = make_mock_response(401, text="Unauthorized")
        mock_session.post.return_value = resp

        client = SigenCloudApiClient(mock_session, "user@test.com", "wrongpass")

        with pytest.raises(SigenCloudAuthError, match="Authentication failed"):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_auth_no_access_token(self, mock_session):
        resp = make_mock_response(200, json_data={"refresh_token": "rt"})
        mock_session.post.return_value = resp

        client = SigenCloudApiClient(mock_session, "user@test.com", "pass")

        with pytest.raises(SigenCloudAuthError, match="No access_token"):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_auth_connection_error(self, mock_session):
        mock_session.post.side_effect = aiohttp.ClientError("DNS fail")

        client = SigenCloudApiClient(mock_session, "user@test.com", "pass")

        with pytest.raises(SigenCloudApiError, match="Connection error during auth"):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_auth_uses_correct_region(self, mock_session):
        resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = resp

        client = SigenCloudApiClient(mock_session, "u", "p", region=REGION_EU)
        await client.authenticate()

        call_args = mock_session.post.call_args
        url = call_args[0][0]
        assert "api-eu.sigencloud.com" in url


# ---------------------------------------------------------------------------
# SigenCloudApiClient — token refresh
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """Tests for _do_refresh_token."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, mock_session):
        # Initial auth
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        client = SigenCloudApiClient(mock_session, "u", "p")
        await client.authenticate()

        # Refresh
        new_tokens = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
        }
        refresh_resp = make_mock_response(200, json_data=new_tokens)
        mock_session.post.return_value = refresh_resp

        await client._do_refresh_token()

        assert client._access_token == "new-access"
        assert client._refresh_token_value == "new-refresh"

    @pytest.mark.asyncio
    async def test_refresh_no_token_raises(self, mock_session):
        client = SigenCloudApiClient(mock_session, "u", "p")
        # No auth performed — no refresh_token

        with pytest.raises(SigenCloudAuthError, match="No refresh token"):
            await client._do_refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_http_error(self, mock_session):
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        client = SigenCloudApiClient(mock_session, "u", "p")
        await client.authenticate()

        fail_resp = make_mock_response(401, text="expired")
        mock_session.post.return_value = fail_resp

        with pytest.raises(SigenCloudAuthError, match="Token refresh failed"):
            await client._do_refresh_token()


# ---------------------------------------------------------------------------
# SigenCloudApiClient — _request
# ---------------------------------------------------------------------------


class TestRequest:
    """Tests for the generic _request method."""

    @pytest.mark.asyncio
    async def test_auto_authenticates(self, mock_session):
        """If no token, _request should call authenticate() first."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": SAMPLE_STATION, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        client = SigenCloudApiClient(mock_session, "u", "p")
        result = await client._request("GET", ENDPOINT_STATION_HOME)

        assert result == SAMPLE_STATION
        mock_session.post.assert_called_once()  # auth call
        mock_session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_bearer_header(self, mock_session):
        """Request must include Authorization: Bearer header."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": {}, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        client = SigenCloudApiClient(mock_session, "u", "p")
        await client._request("GET", "some/path")

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-access-token-12345"

    @pytest.mark.asyncio
    async def test_401_triggers_refresh_then_retry(self, mock_session):
        """On 401, should refresh token and retry once."""
        # Auth
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        # First request returns 401, second returns success
        resp_401 = make_mock_response(401, text="expired")
        resp_ok = make_mock_response(
            200, json_data={"code": 0, "data": {"ok": True}, "message": "success"}
        )

        new_tokens = {"access_token": "refreshed", "refresh_token": "rt2"}
        refresh_resp = make_mock_response(200, json_data=new_tokens)

        mock_session.request.side_effect = [resp_401, resp_ok]
        # post is called for auth, then for refresh
        mock_session.post.side_effect = [auth_resp, refresh_resp]

        client = SigenCloudApiClient(mock_session, "u", "p")
        result = await client._request("GET", "test/path")

        assert result == {"ok": True}
        assert mock_session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_api_error_code(self, mock_session):
        """Non-zero API code should raise SigenCloudApiError."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        api_resp = make_mock_response(
            200, json_data={"code": 500, "data": None, "message": "Internal error"}
        )
        mock_session.request.return_value = api_resp

        client = SigenCloudApiClient(mock_session, "u", "p")

        with pytest.raises(SigenCloudApiError, match="error code 500"):
            await client._request("GET", "fail/path")

    @pytest.mark.asyncio
    async def test_http_non_200_non_401(self, mock_session):
        """Non-200/non-401 HTTP status should raise."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        api_resp = make_mock_response(500, text="Server Error")
        mock_session.request.return_value = api_resp

        client = SigenCloudApiClient(mock_session, "u", "p")

        with pytest.raises(SigenCloudApiError, match="HTTP 500"):
            await client._request("GET", "broken/path")

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_session):
        """aiohttp.ClientError during request should raise SigenCloudApiError."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp

        mock_session.request.side_effect = aiohttp.ClientError("timeout")

        client = SigenCloudApiClient(mock_session, "u", "p")

        with pytest.raises(SigenCloudApiError, match="Connection error"):
            await client._request("GET", "some/path")


# ---------------------------------------------------------------------------
# High-level API methods
# ---------------------------------------------------------------------------


class TestApiMethods:
    """Tests for get_station, get_energy_flow, etc."""

    async def _make_authed_client(self, mock_session):
        """Create an authenticated client."""
        auth_resp = make_mock_response(200, json_data=SAMPLE_AUTH_RESPONSE)
        mock_session.post.return_value = auth_resp
        client = SigenCloudApiClient(mock_session, "u", "p")
        await client.authenticate()
        return client

    @pytest.mark.asyncio
    async def test_get_station(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": SAMPLE_STATION, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        result = await client.get_station()
        assert result["stationId"] == "STATION001"

    @pytest.mark.asyncio
    async def test_get_energy_flow(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": SAMPLE_ENERGY_FLOW, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        result = await client.get_energy_flow("STATION001")
        assert result["pvPower"] == 7.7
        assert result["batterySoc"] == 77.3

        # Verify params
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"] == {"id": "STATION001"}

    @pytest.mark.asyncio
    async def test_get_current_mode(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200,
            json_data={"code": 0, "data": SAMPLE_CURRENT_MODE, "message": "success"},
        )
        mock_session.request.return_value = api_resp

        result = await client.get_current_mode("STATION001")
        assert result["currentMode"] == 0

    @pytest.mark.asyncio
    async def test_get_current_local_weather(self, mock_session):
        client = await self._make_authed_client(mock_session)

        weather_data = {"temperature": 23.1, "humidity": 65}
        api_resp = make_mock_response(
            200,
            json_data={"code": 0, "data": weather_data, "message": "success"},
        )
        mock_session.request.return_value = api_resp

        result = await client.get_current_local_weather("102026031800194")
        assert result == weather_data

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"] == {"stationSnCode": "102026031800194"}

    @pytest.mark.asyncio
    async def test_get_custom_energy_stats(self, mock_session):
        client = await self._make_authed_client(mock_session)

        custom_stats = {"dailyImportEnergy": 9.3, "dailyExportEnergy": 4.1}
        api_resp = make_mock_response(
            200,
            json_data={"code": 0, "data": custom_stats, "message": "success"},
        )
        mock_session.request.return_value = api_resp

        result = await client.get_custom_energy_stats(
            "STATION001",
            "20260407",
            "20260407",
            date_flag=1,
        )
        assert result == custom_stats

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"] == {
            "stationId": "STATION001",
            "startDate": "20260407",
            "endDate": "20260407",
            "dateFlag": 1,
            "resourceIds": "energy_card",
        }

    @pytest.mark.asyncio
    async def test_get_custom_energy_stats_retries_on_500(self, mock_session):
        client = await self._make_authed_client(mock_session)

        fail_resp = make_mock_response(
            500,
            text='{"code":1,"msg":"system error","data":{}}',
        )
        success_resp = make_mock_response(
            200,
            json_data={
                "code": 0,
                "data": {"dailyImportEnergy": 3.2},
                "message": "success",
            },
        )
        mock_session.request.side_effect = [fail_resp, success_resp]

        result = await client.get_custom_energy_stats(
            "STATION001",
            "20260407",
            "20260407",
            date_flag=1,
        )
        assert result["dailyImportEnergy"] == 3.2

        assert mock_session.request.call_count == 2
        first_call = mock_session.request.call_args_list[0]
        second_call = mock_session.request.call_args_list[1]
        assert first_call[0][0] == "GET"
        assert second_call[0][0] == "GET"
        assert first_call[1]["params"] == second_call[1]["params"]
        assert first_call[1]["params"]["stationId"] == "STATION001"
        assert first_call[1]["params"]["resourceIds"] == "energy_card"

    @pytest.mark.asyncio
    async def test_set_operational_mode(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": {}, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        await client.set_operational_mode("STATION001", 5)

        call_args = mock_session.request.call_args
        assert call_args[0][0] == "PUT"
        call_kwargs = call_args[1]
        assert call_kwargs["json"] == {
            "stationId": "STATION001",
            "workingMode": 5,
        }

    @pytest.mark.asyncio
    async def test_set_operational_mode_with_profile(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": {}, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        await client.set_operational_mode("STATION001", 9, profile_id="profile-abc")

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"]["profileId"] == "profile-abc"

    @pytest.mark.asyncio
    async def test_toggle_smart_load_on(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": {}, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        await client.toggle_smart_load("STATION001", "/load/pool", True)

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"] == {"manualSwitch": 1}

    @pytest.mark.asyncio
    async def test_toggle_smart_load_off(self, mock_session):
        client = await self._make_authed_client(mock_session)

        api_resp = make_mock_response(
            200, json_data={"code": 0, "data": {}, "message": "success"}
        )
        mock_session.request.return_value = api_resp

        await client.toggle_smart_load("STATION001", "/load/pool", False)

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"] == {"manualSwitch": 0}

    @pytest.mark.asyncio
    async def test_get_all_data(self, mock_session):
        client = await self._make_authed_client(mock_session)

        ef_resp = make_mock_response(
            200, json_data={"code": 0, "data": SAMPLE_ENERGY_FLOW, "message": "success"}
        )
        mode_resp = make_mock_response(
            200, json_data={"code": 0, "data": SAMPLE_CURRENT_MODE, "message": "success"}
        )
        stats_resp = make_mock_response(
            200,
            json_data={
                "code": 0,
                "data": {"dailyImportEnergy": 8.2},
                "message": "success",
            },
        )
        mock_session.request.side_effect = [ef_resp, mode_resp, stats_resp]

        result = await client.get_all_data("STATION001")

        assert "energy_flow" in result
        assert "current_mode" in result
        assert "energy_stats" in result
        assert result["energy_flow"]["pvPower"] == 7.7
        assert result["current_mode"]["currentMode"] == 0
        assert result["energy_stats"]["dailyImportEnergy"] == 8.2
