"""Command-line utility to run the FastAPI development server."""

import uvicorn


def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the PraktiKit API server."""
    uvicorn.run(
        "praktikit.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_config=None,
    )
