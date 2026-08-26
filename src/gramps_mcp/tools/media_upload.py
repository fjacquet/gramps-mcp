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
Shared local-file-to-Gramps-media upload helper.

Used by create_media_tool (which also merges caller-supplied metadata onto
the result) and by any tool that wants to attach media inline without a
separate create_media round-trip (create_citation_tool, create_source_tool,
create_sourced_event_tool).
"""

import mimetypes
import os

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings

# Reason: the whole file is read into memory before upload, so an unbounded
# read is a denial of service on the MCP process - cap it well above any
# real scan/photo but far below what would exhaust the container's memory.
MAX_MEDIA_BYTES = 100 * 1024 * 1024


def resolve_media_path(file_location: str, import_root: str) -> str:
    """
    Resolve a caller-supplied media path, refusing anything outside the root.

    Args:
        file_location (str): The path the caller asked to upload.
        import_root (str): Directory the path must resolve inside.

    Returns:
        str: The fully resolved path, safe to open.

    Raises:
        FileNotFoundError: When no regular file exists at the path.
        ValueError: When the resolved path lies outside import_root.
    """
    # Reason: realpath resolves symlinks and ".." before the comparison.
    # os.path.isfile alone followed a symlink, so a link inside the root
    # pointing at the server's own .env passed the old check - and the
    # file's bytes then became tree content readable through the media API.
    resolved = os.path.realpath(file_location)
    root = os.path.realpath(import_root)
    # Reason: commonpath raises ValueError for inputs on different drives or
    # a mix of absolute/relative paths - that is not containment, so it must
    # be treated as a refusal, not allowed to crash past the check.
    try:
        inside_root = os.path.commonpath([resolved, root]) == root
    except ValueError:
        inside_root = False
    if not inside_root:
        raise ValueError(
            f"'{file_location}' resolves outside the media import root "
            f"({root}). Copy the file into that directory first."
        )
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"File not found: {file_location}")
    return resolved


async def upload_media_from_path(
    client: GrampsWebAPIClient, file_location: str, tree_id: str
) -> dict:
    """
    Upload a local file to Gramps and return the raw new-media-object dict.

    Pure upload step - no metadata merge. Callers that need to attach
    metadata (description, date, etc.) do so themselves afterward.

    Args:
        client (GrampsWebAPIClient): Client to use for the upload.
        file_location (str): Local path to the file to upload.
        tree_id (str): Family tree identifier.

    Returns:
        dict: The newly created media object as returned by the API,
            including its "handle".
    """
    settings = get_settings()
    resolved = resolve_media_path(file_location, settings.gramps_media_import_root)

    # Reason: the whole file is read into memory before upload, so an
    # unbounded read is a denial of service on the MCP process.
    size = os.path.getsize(resolved)
    if size > MAX_MEDIA_BYTES:
        raise ValueError(
            f"'{file_location}' is {size} bytes, over the "
            f"{MAX_MEDIA_BYTES}-byte upload limit."
        )

    with open(resolved, "rb") as f:
        file_content = f.read()
    mime_type, _ = mimetypes.guess_type(resolved)
    if not mime_type:
        mime_type = "application/octet-stream"

    upload_result = await client.upload_media_file(file_content, mime_type, tree_id)

    if not (
        upload_result and isinstance(upload_result, list) and "new" in upload_result[0]
    ):
        raise GrampsAPIError("Media upload did not return the expected new object.")
    return upload_result[0]["new"]
