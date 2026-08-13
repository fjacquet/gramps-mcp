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
Date parameter model shared by every tool that accepts a Gramps date.
"""

from pydantic import BaseModel, Field, model_validator

# Modifiers whose dateval carries a second date: range and span. Modifiers 7
# (from) and 8 (to) are open-ended single-date modifiers carrying a
# four-element dateval and no stop date. Verified against Gramps'
# is_compound(), which returns True only for modifier 4 and 5.
TWO_DATE_MODIFIERS = (4, 5)


class DateValue(BaseModel):
    """A Gramps date object."""

    dateval: list[int | bool] = Field(
        ...,
        description=(
            "Date values: [day, month, year, False] for a single date, or "
            "[day1, month1, year1, False, day2, month2, year2, False] for a "
            "range or span. Use 0 for an unknown day or month."
        ),
    )
    modifier: int = Field(
        0,
        description=(
            "0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, "
            "6=textonly, 7=from, 8=to"
        ),
    )
    quality: int = Field(0, description="0=regular, 1=estimated, 2=calculated")
    text: str = Field("", description="Free-text date, used when modifier is 6")

    @model_validator(mode="after")
    def check_two_date_modifiers(self) -> "DateValue":
        """
        Reject a range or span that carries only one date.

        Returns:
            DateValue: The validated model.

        Raises:
            ValueError: If a two-date modifier has fewer than eight dateval
                entries.
        """
        # Reason: Gramps accepts the malformed object and only fails later,
        # during the XML export, with IndexError in exportxml.py. Refusing it
        # here turns a corrupted backup into an immediate validation error.
        if self.modifier in TWO_DATE_MODIFIERS and len(self.dateval) < 8:
            raise ValueError(
                f"modifier {self.modifier} needs a second date: dateval must "
                "have 8 entries, [day1, month1, year1, False, day2, month2, "
                "year2, False]. For an approximate single date use quality=1 "
                "with modifier=0 instead."
            )
        return self
