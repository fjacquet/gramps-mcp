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

from pydantic import Field, model_validator

from .base_params import StrictModel

# Modifiers whose dateval carries a second date: range and span. Modifiers 7
# (from) and 8 (to) are open-ended single-date modifiers carrying a
# four-element dateval and no stop date. Verified against Gramps'
# is_compound(), which returns True only for modifier 4 and 5.
TWO_DATE_MODIFIERS = (4, 5)

# Text-only date: content lives in `text`, not `dateval`. Matches
# handlers/date_handler.py:69-71, which special-cases this modifier and
# returns `text` before any `dateval` entry is read.
TEXT_ONLY_MODIFIER = 6


class DateValue(StrictModel):
    """A Gramps date object."""

    dateval: list[int | bool] | None = Field(
        None,
        description=(
            "Date values: [day, month, year, False] for a single date, or "
            "[day1, month1, year1, False, day2, month2, year2, False] for a "
            "range or span. Use 0 for an unknown day or month. May be "
            "omitted when modifier=6 (text-only date), since the content "
            "lives in `text` instead."
        ),
    )
    modifier: int = Field(
        0,
        ge=0,
        le=8,
        description=(
            "0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, "
            "6=textonly, 7=from, 8=to"
        ),
    )
    quality: int = Field(
        0, ge=0, le=2, description="0=regular, 1=estimated, 2=calculated"
    )
    text: str = Field("", description="Free-text date, used when modifier is 6")

    @model_validator(mode="after")
    def check_dateval_matches_modifier(self) -> "DateValue":
        """
        Enforce the dateval shape each modifier requires.

        - Modifier 6 (text-only): dateval may be absent or empty; the date
          lives in `text`.
        - Modifiers 4 and 5 (range, span): dateval must have exactly eight
          entries, the second date bracket.
        - Every other modifier: dateval must have at least four entries.

        Returns:
            DateValue: The validated model.

        Raises:
            ValueError: If dateval does not match the shape its modifier
                requires.
        """
        # Reason: Gramps accepts the malformed object and only fails later,
        # during the XML export, with IndexError in exportxml.py. Refusing it
        # here turns a corrupted backup into an immediate validation error.
        if self.modifier == TEXT_ONLY_MODIFIER:
            return self

        dateval = self.dateval or []

        if self.modifier in TWO_DATE_MODIFIERS:
            if len(dateval) != 8:
                raise ValueError(
                    f"modifier {self.modifier} needs a second date: dateval "
                    "must have exactly 8 entries, [day1, month1, year1, "
                    "False, day2, month2, year2, False]. For an approximate "
                    "single date use quality=1 with modifier=0 instead."
                )
            return self

        if len(dateval) < 4:
            raise ValueError(
                f"modifier {self.modifier} needs dateval with at least 4 "
                "entries, [day, month, year, False]. Use 0 for an unknown "
                "day or month."
            )
        return self
