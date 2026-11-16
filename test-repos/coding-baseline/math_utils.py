def mean(values):
    """Exercise fixture: intentionally incorrect for bug-fix evaluation."""
    if not values:
        raise ValueError("Cannot compute mean of empty list")
    return sum(values) / len(values)
