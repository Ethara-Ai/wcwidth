"""Binary search function for Unicode interval tables."""
from __future__ import annotations


def bisearch(ucs: int, table: tuple[tuple[int, int], ...]) -> int:
    """
    Binary search in interval table.

    :param ucs: Ordinal value of unicode character.
    :param table: Tuple of starting and ending ranges of ordinal values,
        in form of ``((start, end), ...)``.
    :returns: 1 if ordinal value ucs is found within lookup table, else 0.
    """
    pass
