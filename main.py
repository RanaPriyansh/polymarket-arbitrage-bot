"""Polymarket Arbitrage Trading Bot.

A production-ready arbitrage detection service for Polymarket prediction markets.
Provides REST API endpoints for scanning opportunities and getting signals.
"""
import os
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from arbitrage import PolymarketArbitrageBot, ArbitrageOpportunity
from notifications import TelegramNotifier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Polymarket Arbitrage Bot",
    description="Production arbitrage detection service for Polymarket prediction markets",
    version="1.0.0"
)

# Global bot instance
bot: Optional[PolymarketArbitrageBot] = None
telegram_notifier: Optional[TelegramNotifier] = None


class OpportunityResponse(BaseModel):
    """Response model for arbitrage opportunities."""
    opportunities: List[Dict[str, Any]]
    count: int
    scan_time: float
    timestamp: str
    best_opportunity: Optional[Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    bot_initialized: bool
    last_scan: Optional[float]
    opportunities_found: int


def initialize_bot():
    """Initialize the arbitrage bot with credentials."""
    global bot, telegram_notifier

    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        logger.warning("POLYMARKET_PRIVATE_KEY not set - bot will run in limited mode")
        # Use a dummy private key for basic scanning (won't trade)
        private_key = "0xdummy_key_for_scanning_only"

    wallet_address = os.getenv("POLYMARKET_WALLET_ADDRESS")

    bot = PolymarketArbitrageBot(
        private_key=private_key,
        wallet_address=wallet_address
    )
    logger.info("Arbitrage bot initialized")

    # Initialize Telegram notifier if credentials provided
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        telegram_notifier = TelegramNotifier(telegram_token, telegram_chat_id)
        logger.info("Telegram notifier initialized")
    else:
        logger.warning("Telegram credentials not set - alerts disabled")
        telegram_notifier = None

    return bot


@app.on_event("startup")
async def startup_event():
    """Initialize bot on startup."""
    global bot
    bot = initialize_bot()
    logger.info("Arbitrage bot service started")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - service status."""
    return {
        "service": "polymarket-arbitrage-bot",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    if bot is None:
        return HealthResponse(
            status="unhealthy",
            service="polymarket-arbitrage-bot",
            bot_initialized=False,
            last_scan=None,
            opportunities_found=0
        )

    return HealthResponse(
        status="healthy",
        service="polymarket-arbitrage-bot",
        bot_initialized=True,
        last_scan=bot.stats.get("last_scan"),
        opportunities_found=bot.stats.get("opportunities_found", 0)
    )


@app.get("/scan", tags=["Trading"])
async def scan_opportunities(background_tasks: BackgroundTasks) -> OpportunityResponse:
    """
    Scan for arbitrage opportunities across Polymarket.

    Returns a list of potential arbitrage opportunities with profit estimates.
    Can be slow (5-10 seconds) as it queries multiple markets.
    """
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Run scan (could be background for async)
    opportunities = bot.scan_for_opportunities()

    # Send Telegram alerts for high-confidence, high-profit opportunities
    wallet = os.getenv("THIELON_AGENT_WALLET")
    if telegram_notifier and opportunities:
        # Send alert for best opportunity if profit > 2% and confidence > 0.6
        best_opp = bot.get_best_opportunity()
        if best_opp and best_opp.expected_profit_pct > 2.0 and best_opp.confidence > 0.6:
            background_tasks.add_task(
                telegram_notifier.send_opportunity_alert,
                best_opp.to_dict(),
                wallet
            )

    # Get best opportunity
    best_opp = bot.get_best_opportunity()

    return OpportunityResponse(
        opportunities=[opp.to_dict() for opp in opportunities],
        count=len(opportunities),
        scan_time=bot.stats["total_scan_time"],
        timestamp=datetime.utcnow().isoformat() + "Z",
        best_opportunity=best_opp.to_dict() if best_opp else None
    )


@app.get("/opportunities/best", tags=["Trading"])
async def get_best_opportunity():
    """Get the single best arbitrage opportunity."""
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    best_opp = bot.get_best_opportunity()
    if not best_opp:
        return {
            "found": False,
            "message": "No opportunities found in last scan",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    return {
        "found": True,
        "opportunity": best_opp.to_dict(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/stats", tags=["Monitoring"])
async def get_stats():
    """Get bot statistics."""
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    return {
        "service": "polymarket-arbitrage-bot",
        "stats": bot.stats,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/logs", tags=["Monitoring"])
async def get_logs(lines: int = 50):
    """Get recent bot logs (simplified - in production use proper log aggregation)."""
    log_file = "arbitrage_bot.log"

    if not os.path.exists(log_file):
        return {"logs": [], "message": "No log file found yet"}

    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        return {"logs": [], "error": str(e)}

    return {
        "logs": recent_lines,
        "total_lines": len(all_lines),
        "returned": len(recent_lines)
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8080))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        reload=True
    )