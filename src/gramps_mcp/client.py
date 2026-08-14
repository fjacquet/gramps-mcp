# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Unified Gramps Web API client.

This module provides a single client class that uses the unified API call system
for all Gramps Web API operations through the make_api_call method.
"""

import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .auth import AuthManager
from .config import get_api_base_url, get_settings
from .merge import merge_put_data
from .models.api_calls import ApiCalls
from .models.api_mapping import validate_api_call_params

logger = logging.getLogger(__name__)

# Reason: the server's explanation names the offending field, which the generic
# message cannot. Truncated because Gramps can echo the submitted payload, and
# that payload holds genealogy data about living people.
MAX_ERROR_DETAIL = 300


class GrampsAPIError(Exception):
    """Custom exception for Gramps Web API errors."""

    pass


class GrampsWebAPIClient:
    """Unified async HTTP client for all Gramps Web API operations."""

    def __init__(self):
        """Initialize the unified Gramps Web API client."""
        self.settings = get_settings()
        # Use singleton AuthManager - no new instances created
        self.auth_manager = AuthManager()

        self.base_url = get_api_base_url(self.settings)

    async def close(self):
        """Close the HTTP client and auth manager."""
        await self.auth_manager.close()

    async def _get_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        # Use the auth manager's method to get headers with valid token
        await self.auth_manager.get_token()
        return self.auth_manager.get_headers()

    def _build_url(self, tree_id: str, endpoint: str) -> str:
        """Build complete URL for API endpoint."""
        # The tree_id is handled via authentication token, not URL path
        # Ensure base_url ends with / for proper urljoin behavior
        base = self.base_url.rstrip("/") + "/"
        return urljoin(base, endpoint)

    async def _make_request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json_data: dict | None = None,
        retry_auth: bool = True,
        return_headers: bool = False,
        content: bytes | None = None,
        extra_headers: dict | None = None,
        as_text: bool = False,
    ):
        """
        Make HTTP request with error handling and auth retry.

        Args:
            method (str): HTTP method.
            url (str): Absolute request URL.
            params (dict | None): Query string parameters.
            json_data (dict | None): JSON body, used when content is None.
            retry_auth (bool): Whether a 401 may trigger one token refresh.
            return_headers (bool): Return (body, headers) instead of body.
            content (bytes | None): Raw body, sent instead of json_data.
            extra_headers (dict | None): Headers merged over the authentication
                headers, so a caller can override Content-Type.
            as_text (bool): Return the raw response body text instead of
                treating it as JSON. HTTP error handling is unaffected - a
                non-2xx response still raises GrampsAPIError.

        Returns:
            Any: The parsed response body, or a (body, headers) tuple when
                return_headers is set. When as_text is set, the body is the
                raw response text rather than parsed JSON.

        Raises:
            GrampsAPIError: For any HTTP, connection, timeout or parse failure.
        """
        try:
            headers = await self._get_headers()
            if extra_headers:
                headers = {**headers, **extra_headers}
            # Reason: a media upload sends raw bytes with its own Content-Type,
            # so it cannot use the json= path. Everything after the send - the
            # 401 retry, the status formatting, the connect and timeout
            # wrapping, the empty-body case - is identical, which is why the
            # upload routes through here rather than repeating a subset of it.
            response = await self.auth_manager.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data if content is None else None,
                content=content,
                headers=headers,
            )

            # Handle 401 with token refresh retry
            if response.status_code == 401 and retry_auth:
                logger.info("Got 401, refreshing token and retrying")
                await self.auth_manager.authenticate()
                return await self._make_request(
                    method,
                    url,
                    params,
                    json_data,
                    retry_auth=False,
                    return_headers=return_headers,
                    content=content,
                    extra_headers=extra_headers,
                    as_text=as_text,
                )

            response.raise_for_status()

            # Reason: a report download is a file fetch, not a JSON call - the
            # body is HTML/PDF/etc by design, so it must not travel through
            # _parse_response_body's JSON-failure path, which truncates the
            # text to MAX_ERROR_DETAIL for privacy reasons that do not apply
            # to a legitimate, successful, non-JSON response.
            if as_text:
                # Reason: a 2xx with an empty body (e.g. a report request
                # that produced nothing) would otherwise return "" here,
                # which html_to_markdown turns into an empty string that
                # callers wrap in a successful TextContent - the one
                # degenerate success as_text cannot tell apart from a real
                # empty report. Raising surfaces it as an error instead of
                # a silent no-op success.
                if not response.text.strip():
                    raise GrampsAPIError("Empty response body")
                if return_headers:
                    return response.text, dict(response.headers)
                return response.text

            # Handle empty responses
            if not response.text.strip():
                if return_headers:
                    return {}, dict(response.headers)
                return {}

            data = self._parse_response_body(response)
            if return_headers:
                return data, dict(response.headers)
            return data

        except httpx.HTTPStatusError as e:
            error_msg = self._format_http_error(e)
            raise GrampsAPIError(error_msg) from e
        except httpx.ConnectError as e:
            raise GrampsAPIError(f"Cannot connect to Gramps API: {e}") from e
        except httpx.TimeoutException as e:
            raise GrampsAPIError(f"Request timeout: {e}") from e
        except GrampsAPIError:
            # Reason: raised directly above (e.g. the empty-body case for
            # as_text) - re-raise as-is instead of letting the generic
            # handler below wrap it a second time behind an "Unexpected
            # error:" prefix that would obscure the real message.
            raise
        except Exception as e:
            raise GrampsAPIError(f"Unexpected error: {e}") from e

    def _parse_response_body(self, response: httpx.Response) -> Any:
        """
        Parse a successful (2xx) response body as JSON.

        Args:
            response (httpx.Response): The response to parse.

        Returns:
            Any: The parsed JSON body - a dict for most endpoints, but a
                bare list for the Gramps collection and transaction
                endpoints (and the media path), since ``response.json()``
                returns whatever JSON value the server sent. When the body
                does not parse as JSON, a dict describing the failure is
                returned instead, whose ``raw_content`` is bounded by
                MAX_ERROR_DETAIL for the same reason error bodies are
                bounded above: Gramps can echo the submitted payload, which
                may hold genealogy data about living people.
        """
        try:
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            raw_content = response.text
            if len(raw_content) > MAX_ERROR_DETAIL:
                raw_content = raw_content[:MAX_ERROR_DETAIL] + "..."
            return {
                "error": "Invalid JSON response",
                "raw_content": raw_content,
            }

    def _extract_error_detail(self, error: httpx.HTTPStatusError) -> str:
        """
        Pull the server's explanation out of an error response.

        Args:
            error (httpx.HTTPStatusError): The failed response.

        Returns:
            str: The explanation, truncated, or an empty string when the body
                carries nothing useful.
        """
        try:
            body = error.response.json()
        except Exception:
            body = None

        detail = ""
        if isinstance(body, dict):
            for key in ("message", "error", "detail"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
                    break
            if not detail:
                detail = str(body)
        elif body is not None:
            detail = str(body)
        else:
            try:
                detail = error.response.text.strip()
            except Exception:
                detail = ""

        if len(detail) > MAX_ERROR_DETAIL:
            detail = detail[:MAX_ERROR_DETAIL] + "..."
        return detail

    def _format_http_error(self, error: httpx.HTTPStatusError) -> str:
        """
        Convert an HTTP error into a message that names the cause.

        Args:
            error (httpx.HTTPStatusError): The failed response.

        Returns:
            str: A generic sentence categorising the failure, followed by the
                server's own explanation when it sent one.
        """
        status_code = error.response.status_code

        if status_code == 401:
            summary = "Authentication failed. Please check your credentials."
        elif status_code == 403:
            summary = "Permission denied for this operation."
        elif status_code == 404:
            summary = "Record not found."
        elif status_code == 422:
            summary = "Invalid data provided."
        elif status_code >= 500:
            summary = "Server error. Please try again later."
        else:
            summary = f"Request failed with status {status_code}"

        detail = self._extract_error_detail(error)
        if detail:
            return f"{summary} {detail}"
        return summary

    def _build_url_with_substitution(
        self, tree_id: str, endpoint: str, url_params: dict
    ) -> str:
        """
        Build URL with parameter substitution for dynamic endpoints.

        Args:
            tree_id: Family tree identifier
            endpoint: API endpoint with potential placeholders (e.g., "people/{handle}")
            url_params: Parameters to substitute in the endpoint

        Returns:
            Complete URL with parameters substituted
        """
        # Substitute URL parameters in the endpoint
        substituted_endpoint = endpoint
        for param_name, param_value in url_params.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in substituted_endpoint:
                substituted_endpoint = substituted_endpoint.replace(
                    placeholder, str(param_value)
                )

        # Check if all required parameters were provided
        remaining_placeholders = re.findall(r"\{([^}]+)\}", substituted_endpoint)
        if remaining_placeholders:
            raise ValueError(
                f"Missing required URL parameters: {remaining_placeholders}"
            )

        return self._build_url(tree_id, substituted_endpoint)

    async def make_api_call(
        self,
        api_call: ApiCalls,
        params: dict | BaseModel | None = None,
        tree_id: str = "default",
        with_headers: bool = False,
        replace_lists: list[str] | None = None,
        as_text: bool = False,
        **url_params,
    ):
        """
        Make a unified API call using the ApiCalls enum.

        Args:
            api_call: The API call to make from the ApiCalls enum
            params: Parameters for the API call (dict or Pydantic model)
            tree_id: Family tree identifier (default: "default")
            with_headers: Return (body, headers) instead of just the body.
            replace_lists: Keys whose lists should be replaced outright rather
                than merged into the existing record. PUT operations only.
            as_text: Return the raw response body text instead of parsing it
                as JSON. Use for endpoints whose successful response is not
                JSON by design (e.g. an HTML report download) - JSON parsing
                would fail and route the response through the error-truncation
                path meant for genuinely malformed bodies.
            **url_params: URL parameters for endpoint substitution
                (e.g., handle, handle1, handle2)

        Returns:
            API response data

        Raises:
            GrampsAPIError: If the API call fails
            ValueError: If parameters are invalid for the given API call
        """
        # Validate parameters using the mapped parameter model
        validated_params = None
        if params is not None:
            if isinstance(params, BaseModel):
                validated_params = params
            else:
                validated_params = validate_api_call_params(api_call, params)

        # Build the URL with parameter substitution
        endpoint = api_call.endpoint

        # Add tree_id to url_params if endpoint needs it
        if "{tree_id}" in endpoint:
            url_params = dict(url_params)  # Make a copy
            url_params["tree_id"] = tree_id

        url = self._build_url_with_substitution(tree_id, endpoint, url_params)

        # Prepare request parameters
        request_params = None
        json_data = None

        if validated_params is not None:
            params_dict = validated_params.model_dump(exclude_none=True, mode="json")
            # POST and PUT operations use JSON body, GET operations use query parameters
            if (
                api_call.method in ["POST", "PUT"]
                and api_call != ApiCalls.POST_REPORT_FILE
            ):
                json_data = params_dict
            else:
                request_params = params_dict

        # For PUT operations, preserve existing data by merging with changes
        if api_call.method == "PUT" and json_data:
            handle = url_params.get("handle") or json_data.get("handle")
            if handle:
                get_url = self._build_url_with_substitution(
                    tree_id, endpoint, {"handle": handle}
                )
                existing = await self._make_request("GET", get_url)
                if existing:
                    json_data = merge_put_data(existing, json_data, replace_lists)

        # Make the API request
        return await self._make_request(
            method=api_call.method,
            url=url,
            params=request_params,
            json_data=json_data,
            return_headers=with_headers,
            as_text=as_text,
        )

    async def upload_media_file(
        self, file_content: bytes, mime_type: str, tree_id: str = "default"
    ):
        """
        Upload a media file to Gramps.

        Args:
            file_content (bytes): The raw file bytes to upload.
            mime_type (str): The file's MIME type, sent as Content-Type.
            tree_id (str): Family tree identifier (default: "default").

        Returns:
            dict: The parsed JSON response describing the created media object.

        Raises:
            GrampsAPIError: If the upload fails, formatted the same way as
                every other request made through _make_request.
        """
        url = self._build_url(tree_id, "media/")
        return await self._make_request(
            "POST", url, content=file_content, extra_headers={"Content-Type": mime_type}
        )


# Export the main classes for easy import
__all__ = ["GrampsWebAPIClient", "GrampsAPIError"]
