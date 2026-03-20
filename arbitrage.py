"""Arbitrage opportunity detector for Polymarket.

Looks for:
1. Spread opportunities within same market (bid-ask anomalies)
2. Related markets pricing inefficiencies
3. Time-based arbitrage (5min vs 15min vs 1hr)
"""
import os
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import AssetType

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    opportunity_id: str
    market_id: str
    market_name: str
    token_id: str
    strategy: str
    expected_profit_pct: float
    confidence: float
    details: Dict
    timestamp: float

    def to_dict(self):
        return {
            "opportunity_id": self.opportunity_id,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "token_id": self.token_id,
            "strategy": self.strategy,
            "expected_profit_pct": self.expected_profit_pct,
            "confidence": self.confidence,
            "details": self.details,
            "timestamp": self.timestamp,
            "recommended_size": self.details.get("size", 0),
        }


class PolymarketArbitrageBot:
    """Main arbitrage bot class."""

    def __init__(self, private_key: str, wallet_address: Optional[str] = None):
        self.private_key = private_key
        self.wallet_address = wallet_address
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137,  # Polygon
            logger=logger,
        )
        self.opportunities: List[ArbitrageOpportunity] = []
        self.stats = {
            "opportunities_found": 0,
            "total_scan_time": 0.0,
            "last_scan": None,
        }

    def scan_for_opportunities(self) -> List[ArbitrageOpportunity]:
        """Main scan method - runs all arbitrage strategies."""
        start_time = time.time()
        self.opportunities = []

        try:
            # 1. Check for spread arbitrage (bid-ask inconsistencies)
            spread_opps = self._scan_spread_arbitrage()
            self.opportunities.extend(spread_opps)

            # 2. Check for cross-market arbitrage (similar markets)
            cross_opps = self._scan_cross_market()
            self.opportunities.extend(cross_opps)

            # 3. Check for time-window arbitrage
            time_opps = self._scan_time_window_arbitrage()
            self.opportunities.extend(time_opps)

        except Exception as e:
            logger.error(f"Error during scan: {e}")

        self.stats["opportunities_found"] = len(self.opportunities)
        self.stats["total_scan_time"] = time.time() - start_time
        self.stats["last_scan"] = time.time()

        return self.opportunities

    def _scan_spread_arbitrage(self) -> List[ArbitrageOpportunity]:
        """Look for bid-ask spread anomalies in active markets."""
        opportunities = []

        try:
            # Fetch markets (simplified - just get a few for demo)
            markets = self.client.get_markets()
            if not markets or len(markets) < 2:
                return []

            # For each market, get order book
            for market in markets[:10]:  # Limit to first 10 for speed
                market_id = market.get("market_id") or market.get("id")
                market_name = market.get("description") or market.get("question", "Unknown")

                try:
                    order_book = self.client.get_orderbook(market_id)
                    bids = order_book.get("bids", [])
                    asks = order_book.get("asks", [])

                    if not bids or not asks:
                        continue

                    best_bid = float(bids[0]["price"])
                    best_ask = float(asks[0]["price"])
                    spread = best_ask - best_bid

                    # If spread is unusually wide, there might be an arb opportunity
                    # (Buy at bid, sell at ask across multiple token IDs if they represent the same outcome)
                    if spread > 0.05:  # 5% spread threshold
                        opp = ArbitrageOpportunity(
                            opportunity_id=f"spread_{market_id}_{int(time.time())}",
                            market_id=market_id,
                            market_name=market_name,
                            token_id=market_id,
                            strategy="spread_capture",
                            expected_profit_pct=spread * 100,
                            confidence=0.7,
                            details={
                                "bid": best_bid,
                                "ask": best_ask,
                                "spread": spread,
                                "size": min(bids[0]["size"], asks[0]["size"]),
                            },
                            timestamp=time.time(),
                        )
                        opportunities.append(opp)

                except Exception as e:
                    logger.debug(f"Error checking market {market_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in spread scan: {e}")

        return opportunities

    def _scan_cross_market(self) -> List[ArbitrageOpportunity]:
        """Look for arbitrage between correlated markets."""
        opportunities = []

        try:
            markets = self.client.get_markets()
            if not markets:
                return []

            # Group markets by theme (simple keyword matching)
            theme_markets = {}
            for market in markets[:20]:
                desc = market.get("description", "").lower()
                # Extract a theme keyword (e.g., "bitcoin", "btc", "ethereum", "eth")
                keywords = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp"]
                found_keyword = None
                for kw in keywords:
                    if kw in desc:
                        found_keyword = kw
                        break

                if found_keyword:
                    theme_markets.setdefault(found_keyword, []).append(market)

            # For each theme, compare YES prices across related markets
            for theme, mkt_list in theme_markets.items():
                if len(mkt_list) < 2:
                    continue

                prices = []
                for mkt in mkt_list:
                    try:
                        order_book = self.client.get_orderbook(mkt.get("market_id") or mkt.get("id"))
                        bids = order_book.get("bids", [])
                        asks = order_book.get("asks", [])
                        if bids and asks:
                            mid_price = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
                            prices.append((mkt, mid_price))
                    except:
                        continue

                # Check for price discrepancies > 3%
                if len(prices) >= 2:
                    for i in range(len(prices)):
                        for j in range(i + 1, len(prices)):
                            price_diff = abs(prices[i][1] - prices[j][1])
                            avg_price = (prices[i][1] + prices[j][1]) / 2
                            if avg_price > 0 and price_diff / avg_price > 0.03:
                                opp = ArbitrageOpportunity(
                                    opportunity_id=f"cross_{theme}_{int(time.time())}",
                                    market_id=prices[i][0].get("market_id", "unknown"),
                                    market_name=f"{theme} cross-market: {prices[i][0].get('question')} vs {prices[j][0].get('question')}",
                                    token_id="multiple",
                                    strategy="cross_market",
                                    expected_profit_pct=(price_diff / avg_price) * 100,
                                    confidence=0.6,
                                    details={
                                        "price1": prices[i][1],
                                        "price2": prices[j][1],
                                        "market1": prices[i][0].get("question"),
                                        "market2": prices[j][0].get("question"),
                                    },
                                    timestamp=time.time(),
                                )
                                opportunities.append(opp)

        except Exception as e:
            logger.error(f"Error in cross-market scan: {e}")

        return opportunities

    def _scan_time_window_arbitrage(self) -> List[ArbitrageOpportunity]:
        """Look for arbitrage between different time windows (e.g., 5min vs 15min vs 1hr)."""
        opportunities = []

        try:
            markets = self.client.get_markets()
            if not markets:
                return []

            # Group markets by timeframe keywords
            timeframe_groups = {"5min": [], "15min": [], "1hr": [], "other": []}
            for market in markets[:20]:
                desc = market.get("description", "").lower()
                if "5 min" in desc or "5min" in desc or "5-minute" in desc:
                    timeframe_groups["5min"].append(market)
                elif "15 min" in desc or "15min" in desc or "15-minute" in desc:
                    timeframe_groups["15min"].append(market)
                elif "1 hour" in desc or "1hr" in desc or "hour" in desc:
                    timeframe_groups["1hr"].append(market)
                else:
                    timeframe_groups["other"].append(market)

            # Compare same underlying assets across timeframes
            for base_tf in ["5min", "15min", "1hr"]:
                for comp_tf in ["15min", "1hr"]:
                    if base_tf == comp_tf or not timeframe_groups[base_tf] or not timeframe_groups[comp_tf]:
                        continue

                    for base_mkt in timeframe_groups[base_tf][:5]:
                        for comp_mkt in timeframe_groups[comp_tf][:5]:
                            # Simple check: if they're about the same asset
                            base_question = base_mkt.get("question", "").lower()
                            comp_question = comp_mkt.get("question", "").lower()
                            # Check similarity (simple substring match)
                            if any(keyword in base_question and keyword in comp_question
                                   for keyword in ["bitcoin", "btc", "ethereum", "eth", "solana", "xrp"]):
                                try:
                                    base_ob = self.client.get_orderbook(base_mkt.get("market_id") or base_mkt.get("id"))
                                    comp_ob = self.client.get_orderbook(comp_mkt.get("market_id") or comp_mkt.get("id"))

                                    base_bids = base_ob.get("bids", [])
                                    base_asks = base_ob.get("asks", [])
                                    comp_bids = comp_ob.get("bids", [])
                                    comp_asks = comp_ob.get("asks", [])

                                    if not (base_bids and base_asks and comp_bids and comp_asks):
                                        continue

                                    base_mid = (float(base_bids[0]["price"]) + float(base_asks[0]["price"])) / 2
                                    comp_mid = (float(comp_bids[0]["price"]) + float(comp_asks[0]["price"])) / 2

                                    price_diff = abs(base_mid - comp_mid)
                                    avg_price = (base_mid + comp_mid) / 2

                                    if avg_price > 0 and price_diff / avg_price > 0.02:  # 2% threshold
                                        opp = ArbitrageOpportunity(
                                            opportunity_id=f"time_{base_tf}_{comp_tf}_{int(time.time())}",
                                            market_id=base_mkt.get("market_id", "unknown"),
                                            market_name=f"Time arb: {base_mkt.get('question')} ({base_tf}) vs {comp_mkt.get('question')} ({comp_tf})",
                                            token_id="multiple",
                                            strategy="time_window",
                                            expected_profit_pct=(price_diff / avg_price) * 100,
                                            confidence=0.65,
                                            details={
                                                "base_timeframe": base_tf,
                                                "comp_timeframe": comp_tf,
                                                "base_price": base_mid,
                                                "comp_price": comp_mid,
                                            },
                                            timestamp=time.time(),
                                        )
                                        opportunities.append(opp)
                                except Exception as e:
                                    logger.debug(f"Error comparing markets: {e}")
                                    continue

        except Exception as e:
            logger.error(f"Error in time-window scan: {e}")

        return opportunities

    def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """Return the highest confidence opportunity."""
        if not self.opportunities:
            return None
        sorted_opps = sorted(self.opportunities, key=lambda x: (x.confidence, x.expected_profit_pct), reverse=True)
        return sorted_opps[0]
