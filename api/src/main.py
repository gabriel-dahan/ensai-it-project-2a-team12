"""Point d'entrée de l'API DJU."""

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from controllers import dju_controller, user_controller, zone_controller

# .env à la racine du dépôt (api/src/main.py -> ../../.env)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="DJU API",
    description="API de calcul des degrés-jours unifiés (DJU)",
    version="0.1.0",
    root_path=os.getenv("ROOT_PATH", ""),
)

app.include_router(dju_controller.router, prefix="/dju", tags=["DJU"])
app.include_router(zone_controller.router, prefix="/zones", tags=["Zones"])
app.include_router(user_controller.router, prefix="/user", tags=["User"])
app.include_router(zone_controller.user_router, prefix="/user/zones", tags=["Zonings"])


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    """Redirige vers la documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Misc"])
def health_check():
    """Indique que l'API tourne."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("UVICORN_HOST", "0.0.0.0"),
        port=int(os.getenv("UVICORN_PORT", "5001")),
    )
