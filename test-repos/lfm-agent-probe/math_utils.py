def clamp(value, lower, upper):
    """Return value bounded to the inclusive [lower, upper] range."""
    return max(lower, min(value, upper))
