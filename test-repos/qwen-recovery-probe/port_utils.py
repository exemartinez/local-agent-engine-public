def parse_port(value):
    """Return an integer TCP/UDP port in the inclusive range 1..65535."""
    if isinstance(value, int) and 1 <= value <= 65535:
        return value
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValueError("must be a valid port number in the range 1..65535")
    if not (1 <= value <= 65535):
        raise ValueError("must be a valid port number in the range 1..65535")
    return value
