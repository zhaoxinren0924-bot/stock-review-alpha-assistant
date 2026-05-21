"""Stock Review Alpha Assistant - Main Application."""

import os

import rollbar
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rollbar.contrib.fastapi import ReporterMiddleware as RollbarMiddleware
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models import Base, Stock
from app.schemas import StockCreate, StockListResponse, StockResponse

# Initialize Rollbar if token is available
_rollbar_token = os.environ.get("ROLLBAR_ACCESS_TOKEN")
if _rollbar_token:
    rollbar.init(
        _rollbar_token,
        environment=os.environ.get("ROLLBAR_ENVIRONMENT", "development"),
    )

app = FastAPI(
    title="Stock Review Alpha Assistant",
    description="A股基本面复盘智能助手 API",
    version="0.1.0",
)

# CORS for frontend (local dev + Render static site)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://stock-review-web.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rollbar error tracking middleware
if _rollbar_token:
    app.add_middleware(RollbarMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and report to Rollbar."""
    if _rollbar_token:
        rollbar.report_exc_info()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("startup")
async def create_tables():
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - health check."""
    return {"message": "Stock Review Alpha Assistant is running", "status": "ok"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/v1/stocks", response_model=StockListResponse)
async def list_stocks(db: Session = Depends(get_db)) -> StockListResponse:
    """List all tracked stocks."""
    stocks = db.query(Stock).order_by(Stock.created_at.desc()).all()
    return StockListResponse(
        stocks=[StockResponse.model_validate(s) for s in stocks],
        count=len(stocks),
    )


@app.post("/api/v1/stocks", response_model=StockResponse, status_code=201)
async def create_stock(
    stock: StockCreate,
    db: Session = Depends(get_db),
) -> Stock:
    """Add a new stock to the watchlist."""
    existing = db.query(Stock).filter(Stock.code == stock.code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Stock {stock.code} already exists",
        )

    db_stock = Stock(**stock.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


@app.get("/api/v1/stocks/{code}", response_model=StockResponse)
async def get_stock(code: str, db: Session = Depends(get_db)) -> Stock:
    """Get a single stock by code."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {code} not found",
        )
    return stock


@app.delete("/api/v1/stocks/{code}", status_code=204)
async def delete_stock(code: str, db: Session = Depends(get_db)) -> None:
    """Remove a stock from the watchlist."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {code} not found",
        )

    db.delete(stock)
    db.commit()
