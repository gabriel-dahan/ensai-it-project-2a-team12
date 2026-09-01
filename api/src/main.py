"""
Main entry point for the DJU FastAPI web service.

Starts the API and registers the routes used
to calculate Degrés Jours Unifiés (DJU).
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from controllers import dju_controller


app = FastAPI(
    title="DJU API",
    description="API for calculating Degrés Jours Unifiés (DJU)",
    version="0.1.0",
    root_path=os.getenv("ROOT_PATH", ""),
)


app.include_router(
    dju_controller.router,
    prefix="/dju",
    tags=["DJU"],
)


@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    """
    Redirect to the API documentation.
    """
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Misc"])
async def health_check():
    """
    Check that the API is running.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("UVICORN_HOST", "0.0.0.0"),
        port=int(os.getenv("UVICORN_PORT", "5000")),
    )