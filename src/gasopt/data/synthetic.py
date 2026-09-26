"""Fixed pedagogical inputs. THESE ARE NOT EMPIRICAL ETHEREUM OBSERVATIONS."""

from gasopt.types import Scenario, Transaction


def toy_data() -> tuple[tuple[Transaction, ...], tuple[Scenario, ...]]:
    """Return the exact five transactions and five four-slot synthetic paths."""
    transactions = (
        Transaction("tx1", 21_000, 1),
        Transaction("tx2", 65_000, 2),
        Transaction("tx3", 120_000, 4),
        Transaction("tx4", 48_000, 3),
        Transaction("tx5", 180_000, 4),
    )
    paths = ((12, 9, 7, 11), (10, 14, 8, 6), (20, 18, 11, 9),
             (7, 6, 10, 15), (15, 10, 8, 12))
    scenarios = tuple(Scenario(f"s{k}", prices, 0.2) for k, prices in enumerate(paths, 1))
    return transactions, scenarios
