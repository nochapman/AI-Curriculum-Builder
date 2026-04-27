def patch_aiohttp_connector_dns_error() -> None:
    """Patch older aiohttp versions expected by google-genai retry handling."""
    try:
        import aiohttp
    except ImportError:
        return

    if hasattr(aiohttp, "ClientConnectorDNSError"):
        return

    connector_error = getattr(aiohttp, "ClientConnectorError", None)
    if connector_error is not None:
        aiohttp.ClientConnectorDNSError = connector_error
