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
    if not os.path.isfile(file_location):
        raise FileNotFoundError(f"File not found: {file_location}")

    with open(file_location, "rb") as f:
        file_content = f.read()
    mime_type, _ = mimetypes.guess_type(file_location)
    if not mime_type:
        mime_type = "application/octet-stream"

    upload_result = await client.upload_media_file(file_content, mime_type, tree_id)

    if not (
        upload_result and isinstance(upload_result, list) and "new" in upload_result[0]
    ):
        raise GrampsAPIError("Media upload did not return the expected new object.")
    return upload_result[0]["new"]
