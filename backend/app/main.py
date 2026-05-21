"""Stock Review Alpha Assistant - Main Application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Stock Review Alpha Assistant",
    description="A股基本面复盘智能助手 API",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - health check."""
    return {"message": "Stock Review Alpha Assistant is running", "status": "ok"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/v1/stocks")
async def list_stocks() -> JSONResponse:
    """List all tracked stocks."""
    return JSONResponse(
        content={"stocks": [], "count": 0},
        status_code=200,
    )
