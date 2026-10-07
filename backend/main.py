"""App FastAPI — SDD §2.7. Rode a partir de backend/: uvicorn main:app --reload."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.assets import router as assets_router
from api.backtest import router as backtest_router
from api.signals import router as signals_router


def create_app() -> FastAPI:
    app = FastAPI(title="Orus Quant", version="0.1.0")
    # Libera o dashboard web (Vite dev em :5173 ou build servido
    # em outra origem) para chamar a API no navegador.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(assets_router)
    app.include_router(signals_router)
    app.include_router(backtest_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
