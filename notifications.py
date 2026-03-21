"""Telegram notification sender."""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a text message to Telegram."""
        if not self.bot_token or not self.chat_id:
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        try:
            resp = requests.post(url, data=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram message sent: {text[:50]}...")
                return True
            else:
                logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def send_opportunity_alert(self, opportunity: dict, wallet_address: Optional[str] = None):
        """Format and send an arbitrage opportunity alert."""
        profit = opportunity.get('expected_profit_pct', 0)
        strategy = opportunity.get('strategy', 'unknown')
        market = opportunity.get('market_name', 'Unknown market')
        token_id = opportunity.get('token_id', 'N/A')
        size = opportunity.get('recommended_size', 0)

        message = (
            f"🚀 <b>Arbitrage Opportunity Detected</b>\n\n"
            f"<b>Strategy:</b> {strategy}\n"
            f"<b>Market:</b> {market}\n"
            f"<b>Token ID:</b> {token_id}\n"
            f"<b>Expected Profit:</b> {profit:.2f}%\n"
            f"<b>Recommended Size:</b> ${size:.2f}\n"
        )
        if wallet_address:
            message += f"\n<b>Revenue Wallet:</b> <code>{wallet_address}</code>"

        self.send_message(message)