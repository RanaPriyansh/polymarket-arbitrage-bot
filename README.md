# Polymarket Arbitrage Bot

**Cross-market arbitrage scanner for Polymarket prediction markets.**

## Overview

This bot scans for arbitrage opportunities between different markets on Polymarket, focusing on price discrepancies across 5-minute and 15-minute intervals for assets like BTC and ETH.

## Features

- Monitors multiple markets simultaneously
- Detects price differences between time windows
- Generates arbitrage signals with confidence levels
- REST API for integration with trading systems
- Telegram alerts for real-time notifications
- Paper trading mode for testing without execution

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure your API keys
4. Run: `python main.py`

## Deployment

Can be deployed to Railway, Vercel, or any Python hosting platform.

### Railway
1. Connect GitHub repo to Railway
2. Set environment variables (see .env.example)
3. Deploy

### API Endpoints

- `GET /` - Health check
- `GET /opportunities` - Current arbitrage opportunities (JSON)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `POLYMARKET_API_KEY` | API key for Polymarket data |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts (optional) |
| `TELEGRAM_CHAT_ID` | Chat ID for Telegram notifications (optional) |
| `LOG_LEVEL` | Logging level (default: INFO) |

## Status

**Research Phase** – Infrastructure ready; requires API integration and testing.

---
[![GitHub](https://img.shields.io/badge/GitHub-000000?logo=github)](https://github.com/thielon-apps/polymarket-arbitrage-bot)
[![License](https://img.shields.io/github/license/thielon-apps/polymarket-arbitrage-bot)](https://github.com/thielon-apps/polymarket-arbitrage-bot/blob/main/LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/thielon-apps/polymarket-arbitrage-bot)](https://github.com/thielon-apps/polymarket-arbitrage-bot/commits/main)