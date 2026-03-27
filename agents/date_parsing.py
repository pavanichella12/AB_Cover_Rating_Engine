"""
Robust absence-date parsing for mixed exports (ISO + US m/d/y in the same column).
"""

from __future__ import annotations

import pandas as pd

# Try in order; later passes only fill rows still NaT (multiple formats in one column).
_ABSENCE_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%y",
    "%d-%b-%Y",
]


def parse_absence_date_series(ser: pd.Series) -> pd.Series:
    """
    Parse a date column that may mix ISO datetimes and US-style strings in one file.
    """
    if ser is None or len(ser) == 0:
        return pd.to_datetime(ser, errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(ser):
        return ser

    out = pd.Series(pd.NaT, index=ser.index, dtype="datetime64[ns]")
    for fmt in _ABSENCE_DATE_FORMATS:
        need = out.isna()
        if not need.any():
            break
        parsed = pd.to_datetime(ser, format=fmt, errors="coerce")
        fill = need & parsed.notna()
        out.loc[fill] = parsed.loc[fill]

    if out.isna().any():
        rest = ser[out.isna()]
        mixed = pd.to_datetime(rest, errors="coerce", format="mixed")
        out.loc[rest.index] = mixed

    return out
