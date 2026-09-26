"""Operational baseline with no use of future or historical prices."""

from collections.abc import Sequence
from gasopt.types import Transaction


def immediate_schedule(transactions: Sequence[Transaction]) -> dict[str, int]:
    """Execute each transaction at its business-assumed release slot."""
    if len({tx.id for tx in transactions}) != len(transactions):
        raise ValueError("Transaction identifiers must be unique.")
    return {tx.id: tx.release_slot for tx in transactions}
