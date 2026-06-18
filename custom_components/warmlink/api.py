from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import APP_ID, CLOUD_URL, LANGUAGE, REQUEST_CODES
from .models import WarmLinkData, WarmLinkDevice, WarmLinkField

MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")
LOGGER = logging.getLogger(__name__)

REQUEST_RETRY_DELAYS: tuple[int, ...] = (1, 3, 7)
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class WarmLinkApiError(Exception):
    """Raised when the WarmLink API returns an error."""


class WarmLinkAuthError(WarmLinkApiError):
    """Raised when authentication fails."""


class WarmLinkApi:
    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        device_code: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._password_hash = self._hash_password(password)
        self._device_code = device_code
        self._token: str | None = None
        self._device: WarmLinkDevice | None = None

    @property
    def device(self) -> WarmLinkDevice | None:
        return self._device

    @property
    def device_code(self) -> str | None:
        return self._device_code

    def _hash_password(self, raw_password: str) -> str:
        if MD5_RE.match(raw_password):
            return raw_password.lower()

        return hashlib.md5(raw_password.encode("utf-8"), usedforsecurity=False).hexdigest()

    def _app_url(self, endpoint: str) -> str:
        return f"{CLOUD_URL}/app/{endpoint}?lang={LANGUAGE}"

    async def _async_post(
        self,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}

        if token:
            headers["x-token"] = token

        for attempt in range(len(REQUEST_RETRY_DELAYS) + 1):
            try:
                response = await self._session.post(
                    self._app_url(endpoint),
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                break
            except (TimeoutError, ClientError) as err:
                if not _should_retry_http_error(err) or attempt == len(REQUEST_RETRY_DELAYS):
                    raise WarmLinkApiError(f"HTTP error calling {endpoint}: {err}") from err

                delay = REQUEST_RETRY_DELAYS[attempt]
                LOGGER.debug(
                    "Retrying WarmLink request to %s in %s seconds after error: %s",
                    endpoint,
                    delay,
                    err,
                )
                await asyncio.sleep(delay)

        try:
            return await response.json(content_type=None)
        except Exception as err:
            raise WarmLinkApiError(f"Invalid JSON returned by {endpoint}") from err

    def _raise_for_response_error(self, response: dict[str, Any]) -> None:
        error_code = str(response.get("error_code", "0"))
        if error_code in {"0", "", "None"}:
            return

        message = response.get("error_msg") or f"WarmLink API error {error_code}"
        if error_code == "-100":
            raise WarmLinkAuthError(message)

        raise WarmLinkApiError(message)

    async def _async_login(self) -> None:
        payload = {
            "password": self._password_hash,
            "loginSource": "IOS",
            "areaCode": "en",
            "appId": APP_ID,
            "type": "2",
            "userName": self._username,
        }
        response = await self._async_post("user/login", payload)
        self._raise_for_response_error(response)

        token = response.get("objectResult", {}).get("x-token")
        if not token:
            raise WarmLinkAuthError("Login succeeded but no token was returned")

        self._token = token

    async def _async_request(
        self,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._token is None:
            await self._async_login()

        try:
            response = await self._async_post(endpoint, payload, self._token)
            self._raise_for_response_error(response)
            return response
        except WarmLinkAuthError:
            await self._async_login()
            response = await self._async_post(endpoint, payload, self._token)
            self._raise_for_response_error(response)
            return response

    def _parse_devices(self, response: dict[str, Any]) -> list[WarmLinkDevice]:
        devices: list[WarmLinkDevice] = []

        for raw_device in response.get("objectResult") or []:
            code = raw_device.get("deviceCode") or raw_device.get("device_code")
            if not code:
                continue

            name = (
                raw_device.get("deviceNickName")
                or raw_device.get("device_nick_name")
                or raw_device.get("deviceName")
                or raw_device.get("device_name")
                or code
            )
            devices.append(
                WarmLinkDevice(
                    code=code,
                    name=name,
                    model=raw_device.get("custModel") or raw_device.get("model"),
                    serial_number=raw_device.get("sn"),
                    raw=raw_device,
                )
            )

        return devices

    async def async_get_devices(self) -> list[WarmLinkDevice]:
        response = await self._async_request("device/deviceList")
        return self._parse_devices(response)

    async def _async_ensure_device(self) -> WarmLinkDevice:
        if self._device is not None:
            return self._device

        devices = await self.async_get_devices()

        if not devices:
            raise WarmLinkApiError("No WarmLink devices were found on this account")

        if self._device_code is None:
            self._device = devices[0]
            self._device_code = devices[0].code
            return devices[0]

        for device in devices:
            if device.code == self._device_code:
                self._device = device
                return device

        raise WarmLinkApiError(f"Configured device {self._device_code} was not found")

    async def async_fetch_data(self) -> WarmLinkData:
        device = await self._async_ensure_device()
