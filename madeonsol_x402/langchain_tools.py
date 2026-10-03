"""LangChain tools for MadeOnSol API. Install: pip install madeonsol-x402[langchain]"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .client import MadeOnSolClient, MadeOnSolREST


def _client() -> MadeOnSolClient:
    """Create client using env vars. Priority: MADEONSOL_API_KEY > SVM_PRIVATE_KEY."""
    api_key = os.environ.get("MADEONSOL_API_KEY", "")
    private_key = os.environ.get("SVM_PRIVATE_KEY", "")
    if api_key:
        return MadeOnSolClient(api_key=api_key)
    if private_key:
        return MadeOnSolClient(private_key=private_key)
    raise ValueError(
        "Set MADEONSOL_API_KEY — free at https://madeonsol.com/pricing — or SVM_PRIVATE_KEY"
    )


def _rest_client() -> MadeOnSolREST:
    """Create REST client for webhooks/streaming. Requires MADEONSOL_API_KEY."""
    api_key = os.environ.get("MADEONSOL_API_KEY", "")
    if api_key:
        return MadeOnSolREST(api_key=api_key)
    raise ValueError(
        "Set MADEONSOL_API_KEY — free at https://madeonsol.com/pricing — for webhook/streaming features"
    )


class KolFeedInput(BaseModel):
    limit: int = Field(default=10, description="Number of trades (1-100)")
    action: str | None = Field(default=None, description="Filter: 'buy' or 'sell'")


class MadeOnSolKolFeed(BaseTool):
    name: str = "madeonsol_kol_feed"
    description: str = "Get real-time Solana KOL trades from 1,000+ tracked wallets via MadeOnSol. Costs $0.005 USDC per request."
    args_schema: type[BaseModel] = KolFeedInput

    def _run(self, limit: int = 10, action: str | None = None) -> str:
        data = _client().kol_feed(limit=limit, action=action)
        return json.dumps(data, indent=2)


class KolCoordinationInput(BaseModel):
    period: str = Field(default="24h", description="Time period: 1h, 6h, 24h, or 7d")
    min_kols: int = Field(default=3, description="Minimum KOLs converging (2-50)")


class MadeOnSolKolCoordination(BaseTool):
    name: str = "madeonsol_kol_coordination"
    description: str = "Get KOL convergence signals — tokens multiple KOLs are accumulating. Costs $0.02 USDC per request."
    args_schema: type[BaseModel] = KolCoordinationInput

    def _run(self, period: str = "24h", min_kols: int = 3) -> str:
        data = _client().kol_coordination(period=period, min_kols=min_kols)
        return json.dumps(data, indent=2)


class KolLeaderboardInput(BaseModel):
    period: str = Field(
        default="7d",
        description="Time period: today, 7d, 30d, 90d, or 180d (180-day retention)",
    )
    limit: int = Field(default=10, description="Number of KOLs (1-50)")


class MadeOnSolKolLeaderboard(BaseTool):
    name: str = "madeonsol_kol_leaderboard"
    description: str = "Get KOL performance rankings by PnL and win rate. Costs $0.005 USDC per request."
    args_schema: type[BaseModel] = KolLeaderboardInput

    def _run(self, period: str = "7d", limit: int = 10) -> str:
        data = _client().kol_leaderboard(period=period, limit=limit)
        return json.dumps(data, indent=2)


class DeployerAlertsInput(BaseModel):
    limit: int = Field(default=10, description="Number of alerts (1-100)")
    tier: str | None = Field(
        default=None,
        description="Filter by deployer tier: elite, good, moderate, rising, or cold. PRO/ULTRA only — BASIC callers receive 403.",
    )


class MadeOnSolDeployerAlerts(BaseTool):
    name: str = "madeonsol_deployer_alerts"
    description: str = (
        "Get Pump.fun deployer launch alerts with KOL buy enrichment. "
        "PRO/ULTRA subscribers can filter by deployer tier. Costs $0.01 USDC per request."
    )
    args_schema: type[BaseModel] = DeployerAlertsInput

    def _run(self, limit: int = 10, tier: str | None = None) -> str:
        data = _client().deployer_alerts(limit=limit, tier=tier)
        return json.dumps(data, indent=2)


class CreateWebhookInput(BaseModel):
    url: str = Field(description="HTTPS webhook URL to receive events")
    events: str = Field(description="Comma-separated event types: kol:trade, deployer:alert, deployer:bond, kol:coordination")
    min_sol: float | None = Field(default=None, description="Optional: minimum SOL amount filter")


class MadeOnSolCreateWebhook(BaseTool):
    name: str = "madeonsol_create_webhook"
    description: str = "Register a webhook to receive real-time push notifications for KOL trades and deployer alerts. Requires MADEONSOL_API_KEY."
    args_schema: type[BaseModel] = CreateWebhookInput

    def _run(self, url: str, events: str, min_sol: float | None = None) -> str:
        filters = {}
        if min_sol:
            filters["min_sol"] = min_sol
        data = _rest_client().create_webhook(url=url, events=events.split(","), filters=filters or None)
        return json.dumps(data, indent=2)


class ListWebhooksInput(BaseModel):
    pass


class MadeOnSolListWebhooks(BaseTool):
    name: str = "madeonsol_list_webhooks"
    description: str = "List all your registered MadeOnSol webhooks. Requires MADEONSOL_API_KEY."
    args_schema: type[BaseModel] = ListWebhooksInput

    def _run(self) -> str:
        data = _rest_client().list_webhooks()
        return json.dumps(data, indent=2)


class StreamTokenInput(BaseModel):
    pass


class MadeOnSolStreamToken(BaseTool):
    name: str = "madeonsol_stream_token"
    description: str = "Get your WebSocket streaming token for real-time event streaming from MadeOnSol (never expires; same token on every call). Requires MADEONSOL_API_KEY."
    args_schema: type[BaseModel] = StreamTokenInput

    def _run(self) -> str:
        data = _rest_client().get_stream_token()
        return json.dumps(data, indent=2)


class StreamSessionsInput(BaseModel):
    pass


class MadeOnSolStreamSessions(BaseTool):
    name: str = "madeonsol_stream_sessions"
    description: str = "List your live WebSocket sessions (id, service, tier, channels, connected_at, messages_sent) across both stream services. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    args_schema: type[BaseModel] = StreamSessionsInput

    def _run(self) -> str:
        data = _rest_client().stream_sessions()
        return json.dumps(data, indent=2)


class KillStreamSessionInput(BaseModel):
    session_id: int = Field(description="The session id (positive integer) from stream_sessions to evict")


class MadeOnSolKillStreamSession(BaseTool):
    name: str = "madeonsol_kill_stream_session"
    description: str = "Force-terminate one of your live WebSocket sessions and free its connection slot — self-serve fix for a 4002 connection-limit lockout. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    args_schema: type[BaseModel] = KillStreamSessionInput

    def _run(self, session_id: int) -> str:
        data = _rest_client().kill_stream_session(session_id)
        return json.dumps(data, indent=2)


class PriceAlertCreateInput(BaseModel):
    token_mint: str = Field(description="Solana mint address (base58)")
    drop_pct: float = Field(description="Drop % threshold (0.01-99.99). Alert fires when MC drops below baseline × (1 − drop_pct/100).")
    recovery_pct: float | None = Field(default=None, description="Recovery % (0.01-1000). After dip fires, re-fires on recovery. Optional.")
    name: str | None = Field(default=None, description="Optional label")


class MadeOnSolPriceAlertCreate(BaseTool):
    name: str = "madeonsol_price_alert_create"
    description: str = "Create a price alert that fires when a token's MC drops by a specified %. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    args_schema: type[BaseModel] = PriceAlertCreateInput

    def _run(self, token_mint: str, drop_pct: float, recovery_pct: float | None = None, name: str | None = None) -> str:
        data = _rest_client().price_alerts_create(
            token_mint=token_mint, drop_pct=drop_pct,
            recovery_pct=recovery_pct, name=name,
        )
        return json.dumps(data, indent=2)


class PriceAlertsListInput(BaseModel):
    pass


class MadeOnSolPriceAlertsList(BaseTool):
    name: str = "madeonsol_price_alerts_list"
    description: str = "List your price alerts. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    args_schema: type[BaseModel] = PriceAlertsListInput

    def _run(self) -> str:
        data = _rest_client().price_alerts_list()
        return json.dumps(data, indent=2)


class PriceAlertEventsInput(BaseModel):
    alert_id: int | None = Field(default=None, description="Filter to a specific alert")
    event_type: str | None = Field(default=None, description="'dip' or 'recovery'")
    limit: int | None = Field(default=None, description="Max events to return")


class MadeOnSolPriceAlertEvents(BaseTool):
    name: str = "madeonsol_price_alert_events"
    description: str = "Fired price alert event history (30-day retention). Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    args_schema: type[BaseModel] = PriceAlertEventsInput

    def _run(self, alert_id: int | None = None, event_type: str | None = None, limit: int | None = None) -> str:
        data = _rest_client().price_alerts_events(
            alert_id=alert_id, event_type=event_type, limit=limit,
        )
        return json.dumps(data, indent=2)


class ScoutLeaderboardInput(BaseModel):
    limit: int | None = Field(default=None, description="Max entries to return")
    scout_tier: str | None = Field(default=None, description="Filter: S, A, B, or C")
    sort: str | None = Field(default=None, description="Sort: swarm_3plus_pct, n_first_touches_30d, swarm_5plus_pct, scout_score")


class MadeOnSolScoutLeaderboard(BaseTool):
    name: str = "madeonsol_scout_leaderboard"
    description: str = "Scout leaderboard — top KOLs ranked by scout score and swarm attraction rate. PRO+."
    args_schema: type[BaseModel] = ScoutLeaderboardInput

    def _run(self, limit: int | None = None, scout_tier: str | None = None, sort: str | None = None) -> str:
        data = _rest_client().scout_leaderboard(limit=limit, scout_tier=scout_tier, sort=sort)
        return json.dumps(data, indent=2)


class TokenFlowInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")
    window: str = Field(default="1h", description="Rolling window: '1h' or '24h'")


class MadeOnSolTokenFlow(BaseTool):
    name: str = "madeonsol_token_flow"
    description: str = "Token money-flow over a rolling window: unique wallets/buyers/sellers, buy/sell counts, buy/sell SOL, net SOL flow, trades per wallet. PRO+."
    args_schema: type[BaseModel] = TokenFlowInput

    def _run(self, mint: str, window: str = "1h") -> str:
        data = _client().token_flow(mint, window=window)
        return json.dumps(data, indent=2)


class KolConsensusInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")


class MadeOnSolKolConsensus(BaseTool):
    name: str = "madeonsol_kol_consensus"
    description: str = "KOL consensus on a token: buyers/sellers, exit rate, net flow, median entry MC. ULTRA gets wallet arrays."
    args_schema: type[BaseModel] = KolConsensusInput

    def _run(self, mint: str) -> str:
        data = _rest_client().kol_consensus(mint)
        return json.dumps(data, indent=2)


class PeakHistoryInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")


class MadeOnSolPeakHistory(BaseTool):
    name: str = "madeonsol_peak_history"
    description: str = "Peak MC history: ATH, decline from peak %, MC at bond and at 1h/6h/24h/7d after bond."
    args_schema: type[BaseModel] = PeakHistoryInput

    def _run(self, mint: str) -> str:
        data = _rest_client().peak_history(mint)
        return json.dumps(data, indent=2)


class AlmostBondedInput(BaseModel):
    min_progress: float | None = Field(default=None, description="Lower bound on bonding progress % (default 80)")
    min_velocity_pct_per_min: float | None = Field(default=None, description="Minimum Δprogress/min; drops tokens without a 5m snapshot")
    deployer_tier: str | None = Field(default=None, description="Filter by deployer tier: elite/good/moderate/rising/cold/unranked")
    sort: str | None = Field(default=None, description="velocity_desc (default), progress_desc, or eta_asc")
    limit: int | None = Field(default=None, description="Page size (1-100, default 50)")


class MadeOnSolAlmostBonded(BaseTool):
    name: str = "madeonsol_almost_bonded"
    description: str = "Pre-bond pump.fun tokens near graduation, ranked by velocity (Δprogress/min): progress_pct, velocity_pct_per_min, eta_minutes, stalled, deployer_tier. PRO+."
    args_schema: type[BaseModel] = AlmostBondedInput

    def _run(
        self,
        min_progress: float | None = None,
        min_velocity_pct_per_min: float | None = None,
        deployer_tier: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> str:
        data = _rest_client().almost_bonded(
            min_progress=min_progress,
            min_velocity_pct_per_min=min_velocity_pct_per_min,
            deployer_tier=deployer_tier,
            sort=sort,
            limit=limit,
        )
        return json.dumps(data, indent=2)


class WalletBatchClassifyInput(BaseModel):
    wallets: str = Field(description="Comma-separated list of 1-100 base58 wallet addresses to classify")


class MadeOnSolWalletBatchClassify(BaseTool):
    name: str = "madeonsol_wallet_batch_classify"
    description: str = (
        "Bulk wallet reputation flags for 1-100 Solana wallets in ONE call (counts as one request): "
        "per wallet is_sniper / is_bundler / is_dumper / is_kol (+ kol_name), bot_confidence "
        "('none'/'low'/'medium'/'high', null when not alpha-tracked), and a dump_cluster cohort block. "
        "Flags are pump.fun-pipeline scoped — false means NOT OBSERVED in the pipeline, not verified clean. "
        "is_bundler is a lifetime flag; is_dumper uses a rolling 42-day window. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = WalletBatchClassifyInput

    def _run(self, wallets: str) -> str:
        addresses = [w.strip() for w in wallets.split(",") if w.strip()]
        data = _rest_client().wallet_batch_classify(addresses)
        return json.dumps(data, indent=2)


class TokenTradesInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")
    limit: int = Field(default=100, description="Trades per page (1-500, default 100)")
    cursor: str | None = Field(default=None, description="Cursor from previous response's next_cursor field to page older trades")
    action: str | None = Field(default=None, description="Filter: 'buy' or 'sell'")
    wallet: str | None = Field(default=None, description="Filter to a single wallet address (base58)")
    since: int | None = Field(default=None, description="Unix epoch seconds — default full history (starts 2026-04-12)")
    until: int | None = Field(default=None, description="Unix epoch seconds — default now")


class MadeOnSolTokenTrades(BaseTool):
    name: str = "madeonsol_token_trades"
    description: str = (
        "Mint-scoped trade tape — cursor-paginated raw trades for one token, newest first "
        "(the backfill/history complement to the live DEX firehose). Each trade: tx_signature, "
        "wallet_address, action, sol_amount, token_amount, price_sol/price_usd, early_buyer_rank, "
        "slot, block_time, traded_at. Default window is FULL history — capture starts 2026-04-12 "
        "and is pump.fun-pipeline scoped (the response's coverage block carries history_start + scope). "
        "Pass next_cursor from the previous response to page older trades. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenTradesInput

    def _run(
        self,
        mint: str,
        limit: int = 100,
        cursor: str | None = None,
        action: str | None = None,
        wallet: str | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> str:
        data = _rest_client().token_trades(
            mint,
            limit=limit,
            cursor=cursor,
            action=action,
            wallet=wallet,
            since=since,
            until=until,
        )
        return json.dumps(data, indent=2)


class TokenDepthInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")
    sizes: str | None = Field(default=None, description="CSV of SOL buy sizes to quote, e.g. '0.5,1,5,10' (max 8 values, each >0 and <=10000; default 0.5,1,5,10)")


class MadeOnSolTokenDepth(BaseTool):
    name: str = "madeonsol_token_depth"
    description: str = (
        "Per-pool price-impact / slippage depth for a token — how much SOL it takes to move the "
        "price 1%/5%/10% (to_move_price) and the impact per SOL buy size (quotes: size_sol, "
        "tokens_out, avg_price_sol, price_impact_pct), per pool. Constant-product AMMs served from "
        "stream reserves; pump.fun/bonk curves from live virtual reserves. Concentrated pools "
        "(CLMM/Orca/DLMM) land in unsupported_pools with a reason instead of a wrong number. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenDepthInput

    def _run(self, mint: str, sizes: str | None = None) -> str:
        data = _rest_client().token_depth(mint, sizes=sizes)
        return json.dumps(data, indent=2)


class TokenHoldersInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")


class MadeOnSolTokenHolders(BaseTool):
    name: str = "madeonsol_token_holders"
    description: str = (
        "Live holder census + concentration for a token — who holds NOW (not who bought first). "
        "Read live from the ledger: every token account of the mint merged per owner, so "
        "concentration.holder_count is EXACT (null only when the census is not served: provider "
        "refusal for a mega-cap, a timeout, or balances above the mint supply — then a top-20 fallback with source.census_fallback_reason set; never estimated "
        "from trades). Each disclosed owner is labelled from MadeOnSol data (deployer / kol / "
        "early_buyer / bundle / bot / dump_cluster; empty labels = unknown, not clean). Liquidity "
        "pools, bonding curves and burns are EXCLUDED from the circulating denominator and NAMED in "
        "excluded[] (pool + dex + pool_address | bonding_curve | burn | program_account). Amounts "
        "are raw u64 STRINGS. Tier-gated disclosure: PRO 10 / ULTRA 50 / BUSINESS 100. Large "
        "established tokens may first return HTTP 503 holder_scan_in_progress — the scan continues "
        "and is cached, retry after ~20 s. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenHoldersInput

    def _run(self, mint: str) -> str:
        data = _rest_client().token_holders(mint)
        return json.dumps(data, indent=2)


class TokenLocksInput(BaseModel):
    mint: str = Field(description="Token mint address (base58)")
    status: str | None = Field(default=None, description="Filter: 'active' | 'completed' | 'cancelled' | 'closed' (summary always covers all rows)")
    program: str | None = Field(default=None, description="Filter: 'streamflow' | 'jupiter_lock' | 'bonfida_vesting'")
    limit: int | None = Field(default=None, description="1-500, default 200")


class MadeOnSolTokenLocks(BaseTool):
    name: str = "madeonsol_token_locks"
    description: str = (
        "Token locks & vesting on a mint — every on-chain Streamflow / Jupiter Lock / Bonfida "
        "vesting contract with its schedule (start / cliff / period / end), terms (cancelable by "
        "sender or recipient, transferable, top-up) and a live-derived view: locked now, unlocked, "
        "withdrawn, claimable, status, next_unlock. Summary: lock_count, active_count, locked / "
        "deposited totals (raw + ui + usd + pct of supply), unlocking_7d / unlocking_30d forward "
        "schedule, nearest next_unlock, active_cancelable_by_sender (a cancelable lock is a weaker "
        "promise). Answers: did the team lock, how much, until when, can they pull it. Amounts are "
        "base-unit STRINGS; ui/usd/pct null when decimals or price unknown. LP locks NOT included. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenLocksInput

    def _run(self, mint: str, status: str | None = None, program: str | None = None, limit: int | None = None) -> str:
        data = _rest_client().token_locks(mint, status=status, program=program, limit=limit)
        return json.dumps(data, indent=2)


class TokenLocksFeedInput(BaseModel):
    since: str | None = Field(default=None, description="ISO 8601 — only contracts created after this instant (use pagination.next_since)")
    before: str | None = Field(default=None, description="ISO 8601 — page back, only contracts created before this instant")
    mint: str | None = Field(default=None, description="Filter to one mint")
    sender: str | None = Field(default=None, description="Creator / locker wallet")
    recipient: str | None = Field(default=None, description="Recipient wallet")
    program: str | None = Field(default=None, description="'streamflow' | 'jupiter_lock' | 'bonfida_vesting'")
    kind: str | None = Field(default=None, description="'lock' | 'vesting'")
    status: str | None = Field(default=None, description="'active' | 'completed' | 'cancelled' | 'closed'")
    min_usd: float | None = Field(default=None, description="Deposited amount >= USD (needs a known price)")
    min_pct_of_supply: float | None = Field(default=None, description="Deposited amount >= this % of supply (0-100)")
    include_estimated: bool | None = Field(default=None, description="Include backfilled Jupiter Lock rows with no on-chain creation time")
    limit: int | None = Field(default=None, description="1-100, default 50")


class MadeOnSolTokenLocksFeed(BaseTool):
    name: str = "madeonsol_token_locks_feed"
    description: str = (
        "Cross-token feed of NEW token lock / vesting contracts (Streamflow, Jupiter Lock, Bonfida), "
        "newest first — who just locked tokens, of what mint, how much, until when. Same row shape "
        "as the per-mint locks tool plus a token block (symbol, decimals, price_usd, market_cap_usd). "
        "Poll forward with since (cursor pagination.next_since); the same rows are pushed live on "
        "WebSocket channel token:locks. Filters: mint, sender, recipient, program, kind, status, "
        "min_usd, min_pct_of_supply. Amounts are base-unit STRINGS. LP locks NOT included. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenLocksFeedInput

    def _run(
        self,
        since: str | None = None,
        before: str | None = None,
        mint: str | None = None,
        sender: str | None = None,
        recipient: str | None = None,
        program: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        min_usd: float | None = None,
        min_pct_of_supply: float | None = None,
        include_estimated: bool | None = None,
        limit: int | None = None,
    ) -> str:
        data = _rest_client().token_locks_feed(
            since=since,
            before=before,
            mint=mint,
            sender=sender,
            recipient=recipient,
            program=program,
            kind=kind,
            status=status,
            min_usd=min_usd,
            min_pct_of_supply=min_pct_of_supply,
            include_estimated=include_estimated,
            limit=limit,
        )
        return json.dumps(data, indent=2)


class TokenUnlocksInput(BaseModel):
    within: str | None = Field(default=None, description="Window: '1h' | '6h' | '24h' | '3d' | '7d' (default) | '14d' | '30d' | '90d'")
    mint: str | None = Field(default=None, description="Filter to one mint")
    program: str | None = Field(default=None, description="'streamflow' | 'jupiter_lock' | 'bonfida_vesting'")
    kind: str | None = Field(default=None, description="'lock' | 'vesting'")
    min_usd: float | None = Field(default=None, description="Next-event amount >= USD (needs a known price)")
    min_pct_of_supply: float | None = Field(default=None, description="Next-event amount >= this % of supply (0-100)")
    sort: str | None = Field(default=None, description="'soonest' (default) | 'largest_usd' | 'largest_pct'")
    limit: int | None = Field(default=None, description="1-200, default 50")


class MadeOnSolTokenUnlocks(BaseTool):
    name: str = "madeonsol_token_unlocks"
    description: str = (
        "Upcoming token unlock EVENTS across all active lock / vesting contracts inside a window "
        "(1h-90d) — which locked supply hits the market this week, how much, from whose lock. One "
        "entry per active contract = its next unlock event (cliff | period | final | tranche) with "
        "unlock_at, in_seconds, amount (raw / ui / usd / pct of supply) and window_amount_* = that "
        "contract's total release over the whole window, plus the token block and the lock it "
        "belongs to. Continuous per-second streams contribute only cliff / final events. Sort by "
        "soonest, largest_usd or largest_pct. Amounts are base-unit STRINGS. LP locks NOT included. "
        "Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenUnlocksInput

    def _run(
        self,
        within: str | None = None,
        mint: str | None = None,
        program: str | None = None,
        kind: str | None = None,
        min_usd: float | None = None,
        min_pct_of_supply: float | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> str:
        data = _rest_client().token_unlocks(
            within=within,
            mint=mint,
            program=program,
            kind=kind,
            min_usd=min_usd,
            min_pct_of_supply=min_pct_of_supply,
            sort=sort,
            limit=limit,
        )
        return json.dumps(data, indent=2)


class TokenFeeSharesInput(BaseModel):
    mint: str = Field(description="pump.fun coin mint address (base58)")


class MadeOnSolTokenFeeShares(BaseTool):
    name: str = "madeonsol_token_fee_shares"
    description: str = (
        "pump.fun creator-fee sharing on a mint — who the creator fees are redirected to. The "
        "on-chain SharingConfig: admin, status, is_default (true = 100% to the creator, a real "
        "answer), redirected_bps (share going to non-admin addresses), social_bps, and each "
        "shareholder's share_bps, is_admin, is_social_pda (fees earmarked for a platform identity — "
        "social.platform 2 = X, social.user_id = platform-native numeric id, not the handle) and "
        "what it has received. Plus a distributions rollup (every distribute_creator_fees payout, "
        "per-recipient received totals, past recipients), the config change history and "
        "recent_distributions. Amounts are quote base-unit STRINGS (SOL lamports); ui/usd may be "
        "null. Event history starts 2026-08-17. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenFeeSharesInput

    def _run(self, mint: str) -> str:
        data = _rest_client().token_fee_shares(mint)
        return json.dumps(data, indent=2)


class TokenFeeClaimsInput(BaseModel):
    type: str | None = Field(default=None, description="Comma list of event types: distribution, social_claim, shares_created, shares_updated, shares_reset, creator_transferred, creator_claim (default: all except creator_claim)")
    mint: str | None = Field(default=None, description="Filter to one mint")
    recipient: str | None = Field(default=None, description="Payout / claim recipient wallet, or new creator")
    actor: str | None = Field(default=None, description="Transaction signer")
    social_platform: int | None = Field(default=None, description="Raw platform id (2 = X)")
    social_user_id: str | None = Field(default=None, description="Platform-native numeric user id")
    min_sol: float | None = Field(default=None, description="Amount floor in SOL")
    since: str | None = Field(default=None, description="ISO 8601 cursor (use pagination.next_since)")
    before: str | None = Field(default=None, description="ISO 8601 — page back")
    limit: int | None = Field(default=None, description="1-100, default 50")


class MadeOnSolTokenFeeClaims(BaseTool):
    name: str = "madeonsol_token_fee_claims"
    description: str = (
        "pump.fun fee-event feed, newest first: distribution (creator fees paid pro-rata to the "
        "SharingConfig shareholders, with payouts[] per address), social_claim (fees earmarked for a "
        "platform identity — platform 2 = X, user_id = platform-native numeric id — claimed to a "
        "recipient wallet), shares_created / shares_updated / shares_reset (config changes), "
        "creator_transferred, and creator_claim (plain creator vault claim, per creator, no mint — "
        "excluded unless requested via type). Filters: type, mint, recipient, actor, "
        "social_platform, social_user_id, min_sol, since / before. Amounts are quote base-unit "
        "STRINGS (SOL lamports) + amount / amount_usd. The same rows are pushed live on WebSocket "
        "channel token:fee_claims. History starts 2026-08-17. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenFeeClaimsInput

    def _run(
        self,
        type: str | None = None,
        mint: str | None = None,
        recipient: str | None = None,
        actor: str | None = None,
        social_platform: int | None = None,
        social_user_id: str | None = None,
        min_sol: float | None = None,
        since: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> str:
        data = _rest_client().token_fee_claims(
            type=type,
            mint=mint,
            recipient=recipient,
            actor=actor,
            social_platform=social_platform,
            social_user_id=social_user_id,
            min_sol=min_sol,
            since=since,
            before=before,
            limit=limit,
        )
        return json.dumps(data, indent=2)


class TokenSurgesInput(BaseModel):
    kind: str | None = Field(default=None, description="'surge' (token < 30 min old running vs its launch MC) | 'revival' (dormant >= 24 h, then confirmed buys)")
    tier: str | None = Field(default=None, description="Surge tier: 'early' | 'strong' | 'breakout' (surge only — 400 with kind='revival')")
    mint: str | None = Field(default=None, description="Filter to one mint")
    since: str | None = Field(default=None, description="ISO 8601 — only fires after this instant (use pagination.next_since)")
    before: str | None = Field(default=None, description="ISO 8601 — page back (use pagination.next_before)")
    min_mc_usd: float | None = Field(default=None, description="Market cap at fire time >= USD")
    max_mc_usd: float | None = Field(default=None, description="Market cap at fire time <= USD")
    min_buys: int | None = Field(default=None, description="Tape buys at fire time >=")
    launchpad: str | None = Field(default=None, description="Venue at birth: 'pumpfun' | 'launchlab' | 'bags' | ...")
    deployer_tier: str | None = Field(default=None, description="'elite' | 'good' | 'moderate' | 'rising' | 'cold' | 'unranked'")
    exclude_flags: str | None = Field(default=None, description="Comma list of risk flags — rows carrying ANY are dropped (bundled_launch, few_buyers, wash_pattern, thin_liquidity, cold_deployer, sniper_heavy, early_buyers_exiting, sell_pressure, no_tape_trades, no_prior_price, mint_authority_active, transfer_fee)")
    only_clean: bool | None = Field(default=None, description="Only rows with no risk flags at all")
    stats: bool | None = Field(default=None, description="Include per-(kind, tier) hit-rates over `days`")
    days: int | None = Field(default=None, description="Stats window 1-30, default 7")
    limit: int | None = Field(default=None, description="1-200, default 50")


class MadeOnSolTokenSurges(BaseTool):
    name: str = "madeonsol_tokens_surges"
    description: str = (
        "Token surges & revivals — token momentum fires, newest first. kind=surge: a token < 30 min "
        "old whose market cap runs hard vs its LAUNCH MC — tier early (<=10 min, >=$12k, >=3x launch), "
        "strong (<=30 min, >=$30k, >=6x launch and >=2x the 3-min low), breakout (<=2 min, >=$45k, "
        ">=8x); each tier fires once per mint and must be SUSTAINED >=10 s (a one-tick bundle mark is a "
        "spike, not a surge). kind=revival: no 1-minute trade candle for >=24 h, then confirmed by the "
        "tape (>=5 buys, >=$500 buy volume, MC >=1.5x the pre-dormancy close) — never by a price mark; "
        "tier is null. Both need liquidity >=$1.5k and >=2% of MC, and the MC gained must be paid for by "
        "buy volume. Each row: tape (buys/sells/volume; unique_buyers null outside trade coverage), kol "
        "buyers, early_buyers (bundled / sold / sniper wallets), deployer reputation, risk_flags[] "
        "(bundled_launch, few_buyers, wash_pattern, thin_liquidity, cold_deployer, sniper_heavy, "
        "early_buyers_exiting, sell_pressure, no_tape_trades, no_prior_price, mint_authority_active, "
        "transfer_fee — empty = no flag raised, not verified clean), and outcome (+1 h MC / peak / low "
        "multiples) once >=65 min old. stats=true adds per-(kind, tier) hit-rates (up_1h_pct, "
        "median_peak_multiple, doubled_1h_pct) — out-of-sample. Filters kind, tier, mint, launchpad, "
        "deployer_tier, min_mc_usd/max_mc_usd, min_buys, exclude_flags, only_clean; cursors since/before. "
        "The same rows are pushed live on WebSocket channel token:surges (events token:surge / "
        "token:revival). Retention 60 days. Requires MADEONSOL_API_KEY (PRO/ULTRA)."
    )
    args_schema: type[BaseModel] = TokenSurgesInput

    def _run(
        self,
        kind: str | None = None,
        tier: str | None = None,
        mint: str | None = None,
        since: str | None = None,
        before: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
        min_buys: int | None = None,
        launchpad: str | None = None,
        deployer_tier: str | None = None,
        exclude_flags: str | None = None,
        only_clean: bool | None = None,
        stats: bool | None = None,
        days: int | None = None,
        limit: int | None = None,
    ) -> str:
        data = _rest_client().tokens_surges(
            kind=kind,
            tier=tier,
            mint=mint,
            since=since,
            before=before,
            min_mc_usd=min_mc_usd,
            max_mc_usd=max_mc_usd,
            min_buys=min_buys,
            launchpad=launchpad,
            deployer_tier=deployer_tier,
            exclude_flags=exclude_flags,
            only_clean=only_clean,
            stats=stats,
            days=days,
            limit=limit,
        )
        return json.dumps(data, indent=2)


ALL_TOOLS = [
    MadeOnSolKolFeed(),
    MadeOnSolKolCoordination(),
    MadeOnSolKolLeaderboard(),
    MadeOnSolDeployerAlerts(),
    MadeOnSolCreateWebhook(),
    MadeOnSolListWebhooks(),
    MadeOnSolStreamToken(),
    MadeOnSolStreamSessions(),
    MadeOnSolKillStreamSession(),
    MadeOnSolPriceAlertCreate(),
    MadeOnSolPriceAlertsList(),
    MadeOnSolPriceAlertEvents(),
    MadeOnSolScoutLeaderboard(),
    MadeOnSolTokenFlow(),
    MadeOnSolKolConsensus(),
    MadeOnSolPeakHistory(),
    MadeOnSolAlmostBonded(),
    MadeOnSolWalletBatchClassify(),
    MadeOnSolTokenTrades(),
    MadeOnSolTokenDepth(),
    MadeOnSolTokenHolders(),
    MadeOnSolTokenLocks(),
    MadeOnSolTokenLocksFeed(),
    MadeOnSolTokenUnlocks(),
    MadeOnSolTokenFeeShares(),
    MadeOnSolTokenFeeClaims(),
    MadeOnSolTokenSurges(),
]
