"""MadeOnSol API client. Supports MadeOnSol API key (msk_) or x402 micropayments."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import httpx
from importlib.metadata import version as _pkg_version, PackageNotFoundError

# Derive the User-Agent version from the installed package metadata (the single
# source of truth is pyproject.toml) so it can never drift from the manifest.
try:
    _UA_VERSION = _pkg_version("madeonsol-x402")
except PackageNotFoundError:  # running from source without an installed dist
    _UA_VERSION = "0.0.0"

if TYPE_CHECKING:
    from .stream import MadeOnSolStream

BASE_URL = "https://madeonsol.com"


class MadeOnSolClient:
    """MadeOnSol Solana API client.

    Auth priority: api_key > private_key (x402).

    Args:
        api_key: MadeOnSol API key — get one free at https://madeonsol.com/pricing. Preferred.
        private_key: Base58-encoded Solana private key for x402 USDC micropayments (AI agents).
        base_url: API base URL (default: https://madeonsol.com).
    """

    def __init__(
        self,
        private_key: str | None = None,
        base_url: str = BASE_URL,
        *,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth_mode: str = "none"
        self._auth_headers: dict[str, str] = {}
        self._x402: Any = None
        self._api_key = api_key
        self._rest_client: "MadeOnSolREST | None" = None

        if api_key:
            self._auth_mode = "madeonsol"
            self._auth_headers = {"Authorization": f"Bearer {api_key}", "User-Agent": f"madeonsol-x402-python/{_UA_VERSION}"}
        elif private_key:
            self._auth_mode = "x402"
            from x402 import x402Client
            from x402.mechanisms.svm import KeypairSigner
            from x402.mechanisms.svm.exact.register import register_exact_svm_client
            self._x402 = x402Client()
            signer = KeypairSigner.from_base58(private_key)
            register_exact_svm_client(self._x402, signer)
        else:
            import sys
            sys.stderr.write(
                "\n[madeonsol-x402] Missing api_key or private_key.\n"
                "  → Get a free API key (200 req/day, no card) at https://madeonsol.com/pricing\n"
                "  → Then: MadeOnSolClient(api_key=os.environ['MADEONSOL_API_KEY'])\n\n"
            )
            raise ValueError(
                "Provide api_key or private_key. "
                "Get a free API key at https://madeonsol.com/pricing"
            )

    @property
    def rest(self) -> "MadeOnSolREST":
        """REST client for webhook management, streaming tokens, alpha intelligence,
        token quality, copy-trade rules, and wallet tracker.

        Lazily constructed from the same credentials as the parent client.
        Requires `api_key` (x402 mode is not supported for REST endpoints).
        """
        if self._rest_client is None:
            if self._api_key:
                self._rest_client = MadeOnSolREST(api_key=self._api_key, base_url=self.base_url)
            else:
                raise RuntimeError(
                    ".rest requires api_key — x402 mode does not support REST endpoints"
                )
        return self._rest_client

    def _resolve_path(self, path: str) -> str:
        if self._auth_mode == "madeonsol":
            return path.replace("/api/x402/", "/api/v1/")
        return path

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        api_path = self._resolve_path(path)
        if self._auth_mode == "x402":
            from x402.http.clients import x402HttpxClient
            async with x402HttpxClient(self._x402) as http:
                resp = await http.get(f"{self.base_url}{api_path}", params=params)
                resp.raise_for_status()
                return resp.json()
        else:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self.base_url}{api_path}",
                    params=params,
                    headers=self._auth_headers,
                )
                resp.raise_for_status()
                return resp.json()

    def _get_sync(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self._get(path, params)).result()
        return asyncio.run(self._get(path, params))

    # ── Endpoints ──

    def kol_feed(
        self,
        *,
        limit: int = 50,
        before: str | None = None,
        action: str | None = None,
        kol: str | None = None,
        min_sol: float | None = None,
        token_age_max_min: int | None = None,
        exclude_sells: bool | None = None,
        min_kol_winrate: float | None = None,
        strategy: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Real-time KOL trade feed from 1,000+ wallets.

        Args:
            limit: Max trades to return.
            before: Cursor — ISO 8601 timestamp; returns trades strictly older
                than this. Pass ``next_before`` from the previous response for
                incremental polling.
            action: Filter by 'buy' or 'sell'.
            kol: Filter by KOL handle/name.
            min_sol: PRO+ — minimum SOL size per trade.
            token_age_max_min: PRO+ — max token age in minutes at trade time.
            exclude_sells: PRO+ — drop sell-side trades.
            min_kol_winrate: PRO+ — minimum 7d winrate of the KOL (0-100).
            strategy: PRO+ — 'scalper', 'day_trader', 'swing_trader', 'hodler', or 'mixed'.
            min_mc_usd: v1.6 — lower bound on market_cap_usd_at_trade. Drops
                trades with unknown MC when set.
            max_mc_usd: v1.6 — upper bound on market_cap_usd_at_trade.
        """
        params: dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before
        if action:
            params["action"] = action
        if kol:
            params["kol"] = kol
        if min_sol is not None:
            params["min_sol"] = min_sol
        if token_age_max_min is not None:
            params["token_age_max_min"] = token_age_max_min
        if exclude_sells:
            params["exclude_sells"] = "true"
        if min_kol_winrate is not None:
            params["min_kol_winrate"] = min_kol_winrate
        if strategy:
            params["strategy"] = strategy
        if min_mc_usd is not None:
            params["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None:
            params["max_mc_usd"] = max_mc_usd
        return self._get_sync("/api/x402/kol/feed", params)

    def kol_coordination(
        self,
        *,
        period: str = "24h",
        min_kols: int = 3,
        limit: int = 20,
        min_avg_winrate: float | None = None,
        unique_strategies: int | None = None,
        include_majors: bool | None = None,
        window_minutes: int | None = None,
        min_score: int | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """KOL convergence signals (v1.1 — peak-density + score).

        Args:
            period: '1h', '6h', '24h', or '7d'.
            min_kols: Minimum KOLs in a cluster.
            limit: Max clusters to return.
            min_avg_winrate: PRO+ — require cluster avg winrate_7d >= N (0-100).
            unique_strategies: PRO+ — require cluster to span >= N strategies.
            include_majors: v1.1 — include WIF/BONK/POPCAT etc. Default False.
            window_minutes: v1.1 — peak-density window size (1-60). Default 15.
            min_score: v1.1 — minimum composite coordination score (0-100).

        Response (v1.1): each token includes peak_window_start/end, peak_kols,
        peak_buys, exited_count, holders_count, coordination_score, and per-KOL
        buy_sol/sell_sol/exited (PRO+).
        """
        params: dict[str, Any] = {"period": period, "min_kols": min_kols, "limit": limit}
        if min_avg_winrate is not None:
            params["min_avg_winrate"] = min_avg_winrate
        if unique_strategies is not None:
            params["unique_strategies"] = unique_strategies
        if include_majors is not None:
            params["include_majors"] = "true" if include_majors else "false"
        if window_minutes is not None:
            params["window_minutes"] = window_minutes
        if min_score is not None:
            params["min_score"] = min_score
        if min_mc_usd is not None:
            params["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None:
            params["max_mc_usd"] = max_mc_usd
        return self._get_sync("/api/x402/kol/coordination", params)

    def kol_leaderboard(
        self,
        *,
        period: str = "7d",
        limit: int = 20,
        sort: str | None = None,
        strategy: str | None = None,
        min_winrate: float | None = None,
    ) -> dict[str, Any]:
        """KOL PnL/win-rate rankings.

        Args:
            period: One of 'today', '7d', '30d', '90d', '180d'. Trade history is
                retained for 180 days; long windows fill up over time.
            limit: Max KOLs to return.
            sort: PRO+ — 'pnl' (default), 'winrate', 'profit_factor', 'roi', or 'early_entry'.
            strategy: PRO+ — filter by 'sniper', 'flipper', 'swinger', 'holder', 'mixed'.
            min_winrate: PRO+ — minimum winrate cutoff (0-100).
        """
        params: dict[str, Any] = {"period": period, "limit": limit}
        if sort:
            params["sort"] = sort
        if strategy:
            params["strategy"] = strategy
        if min_winrate is not None:
            params["min_winrate"] = min_winrate
        return self._get_sync("/api/x402/kol/leaderboard", params)

    def deployer_alerts(
        self,
        *,
        limit: int = 20,
        since: str | None = None,
        before: str | None = None,
        offset: int = 0,
        tier: str | None = None,
        alert_type: str | None = None,
        priority: str | None = None,
        min_kol_buys: int | None = None,
    ) -> dict[str, Any]:
        """Pump.fun deployer alerts with KOL buy enrichment.

        Each alert item includes ``deployer_sol_balance`` (float | None) — the
        deployer wallet's SOL balance captured at alert time; ``None`` for
        historical rows recorded before this field existed.

        Args:
            limit: Max alerts to return.
            since: Optional ISO8601 timestamp — only alerts created after this.
            before: Cursor — ISO 8601 timestamp; returns alerts strictly older
                than this. Preferred over ``offset`` at scale.
            offset: Legacy pagination offset (prefer ``before``).
            tier: Filter by deployer tier ('elite', 'good', 'moderate', 'rising',
                'cold'). **PRO/ULTRA subscribers only** — BASIC callers passing
                this receive HTTP 403.
            alert_type: Filter by alert_type (e.g. 'new_deploy', 'bonded').
            priority: Filter by 'high', 'medium', or 'low'.
            min_kol_buys: Only alerts where at least N KOLs bought the token.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if since:
            params["since"] = since
        if before:
            params["before"] = before
        if tier:
            params["tier"] = tier
        if alert_type:
            params["alert_type"] = alert_type
        if priority:
            params["priority"] = priority
        if min_kol_buys is not None:
            params["min_kol_buys"] = min_kol_buys
        return self._get_sync("/api/x402/deployer-hunter/alerts", params)

    def kol_pairs(
        self, *, period: str = "7d", min_shared: int = 3, limit: int = 20
    ) -> dict[str, Any]:
        """KOL affinity matrix — which KOLs co-trade the same tokens."""
        return self._get_sync("/api/x402/kol/pairs", {
            "period": period, "min_shared": min_shared, "limit": limit,
        })

    def kol_hot_tokens(
        self,
        *,
        period: str = "6h",
        min_kols: int = 1,
        limit: int = 20,
        min_avg_winrate: float | None = None,
        unique_strategies: int | None = None,
    ) -> dict[str, Any]:
        """KOL momentum tokens — accelerating KOL buy interest.

        Args:
            period: '1h' or '6h'.
            min_kols: Minimum distinct KOL buyers.
            limit: Max tokens to return.
            min_avg_winrate: PRO+ — require avg winrate_7d of buyers >= N (0-100).
            unique_strategies: PRO+ — require >= N distinct strategies among buyers.
        """
        params: dict[str, Any] = {"period": period, "min_kols": min_kols, "limit": limit}
        if min_avg_winrate is not None:
            params["min_avg_winrate"] = min_avg_winrate
        if unique_strategies is not None:
            params["unique_strategies"] = unique_strategies
        return self._get_sync("/api/x402/kol/tokens/hot", params)

    def kol_trending_tokens(
        self, *, period: str = "1h", min_kols: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        """Tokens ranked by KOL buy volume. Sub-hour periods require PRO/ULTRA."""
        return self._get_sync("/api/x402/kol/tokens/trending", {
            "period": period, "min_kols": min_kols, "limit": limit,
        })

    def kol_token_entry_order(
        self, mint: str, *, limit: int = 50
    ) -> dict[str, Any]:
        """Ranked KOL first-buyers for a token.

        Returns each KOL's first buy ordered by traded_at, with seconds_after_first
        relative to the first KOL entry. PRO+ adds percentile_pnl_7d per entry.
        """
        return self._get_sync(
            f"/api/x402/kol/tokens/{mint}/entry-order", {"limit": limit}
        )

    def kol_compare_wallets(self, wallets: list[str]) -> dict[str, Any]:
        """Side-by-side comparison of 2-5 KOL wallets.

        Args:
            wallets: 2-5 wallet addresses. BASIC=2, PRO=4, ULTRA=5.
        PRO+ adds an `overlap` list of tokens bought by 2+ of the wallets in 30d.
        """
        return self._get_sync("/api/x402/kol/compare", {"wallets": ",".join(wallets)})

    def kol_alerts_recent(
        self,
        *,
        window: str = "15m",
        types: list[str] | None = None,
        min_severity: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Live KOL alert feed.

        Args:
            window: '5m', '15m', '1h', '6h', or '24h'. Default '15m'.
            types: Subset of 'consensus_cluster', 'fresh_token_kol_buy', 'heating_up'.
            min_severity: 'low', 'medium', or 'high'.
            limit: Max alerts to return.
        """
        params: dict[str, Any] = {"window": window, "limit": limit}
        if types:
            params["types"] = ",".join(types)
        if min_severity:
            params["min_severity"] = min_severity
        return self._get_sync("/api/x402/kol/alerts/recent", params)

    def wallet_stats(self, address: str) -> dict[str, Any]:
        """Universal wallet stats over 90d for any Solana wallet plus cross-product flags
        (is_kol + kol_name, is_alpha_tracked + bot_confidence + win_rate + net_pnl,
        is_deployer + tokens_deployed). Works on any wallet, not just curated KOLs.
        **x402: $0.005**.

        v1.22 — ``flags`` also carries reputation flags ``is_sniper`` /
        ``is_bundler`` / ``is_dumper`` plus a ``dump_cluster`` block
        (``dump_cohorts``, ``runner_cohorts``, ``total_cohorts``, ``as_of``;
        ``None`` when the wallet has no dump-cluster record). ``bot_confidence``
        is a string enum ``'none'`` | ``'low'`` | ``'medium'`` | ``'high'`` (or
        ``None`` when not alpha-tracked) — earlier docs said number, and a
        server bug made it always ``None``; it now returns real values.
        Scope caveat: reputation flags derive from the pump.fun trade pipeline —
        ``False`` means "not observed", NOT verified clean; ``is_bundler`` is a
        lifetime flag, ``is_dumper`` uses a rolling 42-day window.

        Args:
            address: Base58 wallet address (32-44 chars).
        """
        return self._get_sync(f"/api/x402/wallet/{address}")

    def wallet_pnl(self, address: str) -> dict[str, Any]:
        """Full FIFO cost-basis PnL: realized + unrealized SOL, profit factor, max
        drawdown, hold-time stats, daily UTC PnL curve, closed positions sorted
        by pnl desc, open positions with live unrealized P&L from the market-cap
        tracker. Cached server-side — cache hits return immediately. **x402: $0.02**.

        Args:
            address: Base58 wallet address.
        """
        return self._get_sync(f"/api/x402/wallet/{address}/pnl")

    def wallet_positions(self, address: str) -> dict[str, Any]:
        """Open positions only — lighter slice of `wallet_pnl`. Shares the same cache.
        **x402: $0.01**.

        Args:
            address: Base58 wallet address.
        """
        return self._get_sync(f"/api/x402/wallet/{address}/positions")

    def wallet_trades(
        self,
        address: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        action: str | None = None,
        token_mint: str | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> dict[str, Any]:
        """Cursor-paginated raw trades for any wallet (last 90 days by default).
        **x402: $0.005** per page.

        Since 2026-08-16 each trade also carries ``price_sol``/``price_usd``
        (that trade's executed price, ``sol_amount / token_amount``) and
        ``market_price_sol``/``market_price_usd`` (the canonical pool price near
        its slot) — this route previously returned amounts and no price at all.
        Same definitions as :meth:`token_trades`.

        Args:
            address: Base58 wallet address.
            limit: 1-500, default 100.
            cursor: From `next_cursor` of a previous response.
            action: 'buy' or 'sell' filter.
            token_mint: Filter to a single token.
            since: Unix epoch seconds (default now-90d).
            until: Unix epoch seconds (default now).
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if action is not None:
            params["action"] = action
        if token_mint is not None:
            params["token_mint"] = token_mint
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        return self._get_sync(f"/api/x402/wallet/{address}/trades", params)

    def scout_leaderboard(
        self,
        *,
        limit: int | None = None,
        scout_tier: str | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """v1.9 — Scout leaderboard: top KOLs ranked by scout score, first-touch
        frequency, and swarm attraction rate. ULTRA only.

        Args:
            limit: Max entries to return.
            scout_tier: Filter to 'S', 'A', 'B', or 'C'.
            sort: 'swarm_3plus_pct', 'n_first_touches_30d', 'swarm_5plus_pct', or 'scout_score'.
        """
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        if scout_tier is not None: params["scout_tier"] = scout_tier
        if sort is not None: params["sort"] = sort
        return self._get_sync("/api/x402/kol/scouts/leaderboard", params or None)

    def coordination_history(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
        min_score: int | None = None,
    ) -> dict[str, Any]:
        """v1.9 — Coordination history: past coordination alert fires with token,
        score, KOL count. ULTRA only.

        Args:
            limit: Max entries.
            since: ISO 8601 — events after this timestamp.
            min_score: Minimum coordination score.
        """
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        if since is not None: params["since"] = since
        if min_score is not None: params["min_score"] = min_score
        return self._get_sync("/api/x402/kol/coordination/history", params or None)

    def kol_consensus(self, mint: str) -> dict[str, Any]:
        """v1.9 — KOL consensus on a token: buyers/sellers, exit rate, net flow,
        median entry MC. ULTRA gets individual wallet arrays.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/kol-consensus")

    def peak_history(self, mint: str) -> dict[str, Any]:
        """v1.9 — Peak MC history: ATH, decline from peak, MC at bond and at
        1h/6h/24h/7d after bond.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/peak-history")

    def token_flow(self, mint: str, *, window: str = "1h") -> dict[str, Any]:
        """v1.17 — Token money-flow over a rolling window. PRO+ (keyed).

        Aggregates buy/sell pressure for a token across the window into unique
        wallet/buyer/seller counts, buy/sell trade counts, SOL volume per side,
        net SOL flow, and trades-per-wallet.

        Returns a dict with keys: ``mint``, ``window``, ``from``,
        ``unique_wallets``, ``unique_buyers``, ``unique_sellers``,
        ``buy_count``, ``sell_count``, ``total_trades``, ``buy_sol``,
        ``sell_sol``, ``net_sol``, ``trades_per_wallet``.

        Args:
            mint: Token mint address.
            window: Rolling window — '1h' or '24h' (default '1h').
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/flow", {"window": window})

    async def token_flow_async(self, mint: str, *, window: str = "1h") -> dict[str, Any]:
        """Async variant of :meth:`token_flow`. See that method for details."""
        return await self._get(f"/api/x402/tokens/{mint}/flow", {"window": window})

    def token_risk(self, mint: str) -> dict[str, Any]:
        """Transparent 0–100 token safety/rug-risk score with a per-factor
        breakdown (liquidity, mint/freeze authority, LP status, holder
        concentration) — the "is this safe to buy?" decision call.

        v1.22 — ``inputs`` gains ``sniper_footprint``: the slot-window
        launch-snipe rollup (``buys``, ``buyers``, ``sol``, ``supply_pct``,
        ``sniper_wallet_buys``, ``data_available``, ``as_of``; buys landing in
        slots deploy-1..deploy+3). ``None`` = no rollup yet;
        ``data_available=False`` = mint not observable in the trade pipeline —
        NOT zero snipes.

        v1.23 — the response gains a top-level ``dev`` object (deployer
        self-activity: ``wallet``, ``launchpad``, ``deployed_at``, ``buy_sol``,
        ``buy_tokens``, ``buy_supply_pct``, ``bought_tokens_after``,
        ``sold_tokens``, ``sold_sol``, ``first_sell_at``, ``last_sell_at``,
        live ``holdings_tokens`` / ``holdings_supply_pct``, ``wallet_empty``,
        ``transfer_status`` -- suspected / none_detected / unknown; ``transferred_out``
        is its deprecated boolean view) plus ``as_of``. ``dev`` is ``None`` when the mint
        has no tracked deploy row. Score v2 (2026-09-21): ``assessment`` lists
        ``unknown_inputs`` / ``not_assessed``; a token-supply burn is never LP evidence;
        a failed score-critical read is HTTP 503 ``risk_inputs_unavailable``.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/risk")

    def token_buyer_quality(self, mint: str) -> dict[str, Any]:
        """Early-buyer quality score (dump-cluster exposure, recycled-wallet
        rate, smart-money presence) with the live, out-of-sample Signal
        Scorecard efficacy stat attached.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/buyer-quality")

    def token(self, mint: str) -> dict[str, Any]:
        """Live token snapshot — price, market cap, FDV, liquidity, and DEX metadata.

        Returns ``{ "token": {...} }`` with ``price_usd``/``price_sol``,
        ``market_cap``, ``fdv_usd``, ``liquidity_usd``, ``liquidity_to_mc_ratio``,
        ``primary_dex``, ``is_token_2022``, ``transfer_fee_bps``, and a
        ``top_buyers`` array of ``{name, sol_amount}``.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/token/{mint}")

    def signal_performance(self, name: str, *, history: bool = False) -> dict[str, Any]:
        """Signal Scorecard — out-of-sample reliability for a named signal.

        Returns the signal's ``hit_rate``, ``base_rate``, ``lift``, ``sample_n``,
        ``window_days``, and ``test_from``/``test_to`` reliability buckets, plus
        ``signal``, ``metric_type``, ``outcome``, ``methodology``, and ``as_of``.
        Pass ``history=True`` to additionally get a per-day series.

        Args:
            name: One of 'dump_cluster_count', 'runner_rate',
                'recycled_early_buyer_count', or 'coordination_count'.
            history: When True, include the per-day performance series.
        """
        params = {"history": "true"} if history else None
        return self._get_sync(f"/api/x402/signals/{name}/performance", params)

    def signals(self) -> dict[str, Any]:
        """Free — signal catalog: name, description, and each signal's methodology
        and ``performance_endpoint``, plus a ``docs`` link.
        """
        return self._get_sync("/api/x402/signals")

    # ── v1.22 — endpoints newly added to the keyless x402 catalog (18 → 25).
    # Each also works in api_key mode (the /api/x402/ prefix is rewritten to
    # /api/v1/). Keyed REST equivalents live on MadeOnSolREST.

    def token_candles(
        self,
        mint: str,
        *,
        tf: str = "1h",
        limit: int = 200,
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, Any]:
        """v1.22 — OHLCV candles, now keyless. **x402: $0.01**.

        Same shape as :meth:`MadeOnSolREST.token_candles` — see that method for
        the full field list. Keyless callers get the PRO slice (OHLCV, last 30
        days).

        Args:
            mint: Token mint address.
            tf: '1m' | '5m' | '15m' | '1h' | '4h' | '1d' (default '1h').
            limit: Candles to return, 1-1000 (default 200).
            from_: Optional ISO8601 start (maps to the ``from`` query param).
            to: Optional ISO8601 end.
        """
        params: dict[str, Any] = {"tf": tf, "limit": limit}
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        return self._get_sync(f"/api/x402/tokens/{mint}/candles", params)

    def almost_bonded(self, **filters: Any) -> dict[str, Any]:
        """v1.22 — Pre-bond pump.fun tokens near graduation, now keyless.
        **x402: $0.01**.

        Same params and shape as :meth:`MadeOnSolREST.almost_bonded`
        (``min_progress``, ``max_progress``, ``min_velocity_pct_per_min``,
        ``max_age_minutes``, ``deployer_tier``, ``authority_revoked``,
        ``min_liq``, ``sort``, ``limit``).
        """
        params: dict[str, Any] = {}
        for key, val in filters.items():
            if val is None:
                continue
            params[key] = "true" if val is True else "false" if val is False else val
        return self._get_sync("/api/x402/tokens/almost-bonded", params or None)

    def token_top_traders(
        self,
        mint: str,
        *,
        limit: int | None = None,
        sort: str | None = None,
        window_days: int | None = None,
        min_bought_sol: float | None = None,
    ) -> dict[str, Any]:
        """v1.22 — Wallets ranked by realized PnL (or ROI) on a token, enriched
        with KOL identity and alpha-wallet reputation. **x402: $0.02**.

        Args:
            mint: Token mint address.
            limit: Max traders to return.
            sort: 'pnl' (default) or 'roi'.
            window_days: Trade lookback window in days.
            min_bought_sol: Minimum SOL bought to qualify (default 0.1).
        """
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        if sort is not None: params["sort"] = sort
        if window_days is not None: params["window_days"] = window_days
        if min_bought_sol is not None: params["min_bought_sol"] = min_bought_sol
        return self._get_sync(f"/api/x402/tokens/{mint}/top-traders", params or None)

    def token_cap_table(self, mint: str) -> dict[str, Any]:
        """v1.22 — Early-buyer cap table (first non-deployer buyers with PnL,
        exit status, bundle/KOL/alpha flags), now keyless. **x402: $0.02**.

        Args:
            mint: Token mint address.
        """
        return self._get_sync(f"/api/x402/tokens/{mint}/cap-table")

    def sniper_recent(
        self,
        *,
        since: str | None = None,
        deployer_tier: str | None = None,
        min_bond_rate: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """v1.22 — Deshred pre-confirm pump.fun deploy feed, now keyless
        (elite/good scope). **x402: $0.01**.

        Each deploy carries ``footprint`` — the slot-window snipe rollup
        (``buys``, ``buyers``, ``sol``, ``supply_pct``, ``sniper_wallet_buys``,
        ``data_available``, ``as_of``) or ``None`` when not yet settled /
        observable. Keyed callers: PRO sees elite/good, ULTRA all tiers +
        watchlist — see :meth:`MadeOnSolREST.sniper_recent`.
        """
        params: dict[str, Any] = {}
        if since is not None: params["since"] = since
        if deployer_tier is not None: params["deployer_tier"] = deployer_tier
        if min_bond_rate is not None: params["min_bond_rate"] = min_bond_rate
        if limit is not None: params["limit"] = limit
        return self._get_sync("/api/x402/sniper/recent", params or None)

    def deployer_trajectory(self, wallet: str) -> dict[str, Any]:
        """v1.22 — Deployer skill curve (streaks, rolling bond rate, trend),
        now keyless. **x402: $0.01**.

        Args:
            wallet: Deployer wallet address.
        """
        return self._get_sync(f"/api/x402/deployer-hunter/{wallet}/trajectory")

    def discovery(self) -> dict[str, Any]:
        """Free — list all endpoints and prices (25 keyless x402 endpoints)."""
        resp = httpx.get(f"{self.base_url}/api/x402")
        resp.raise_for_status()
        return resp.json()


class MadeOnSolREST:
    """REST API client for the full v1 surface — webhooks, streaming, alpha
    intelligence, token quality, copy-trade rules, wallet tracker.

    Args:
        api_key: MadeOnSol API key (msk_...). Required.
        base_url: API base URL (default: https://madeonsol.com).

    The most recent response's rate-limit headers are exposed via `last_rate_limit`:
        {'limit': int|None, 'remaining': int|None, 'reset': int|None, 'request_id': str|None}
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if not api_key:
            import sys
            sys.stderr.write(
                "\n[madeonsol-x402] MadeOnSolREST: missing api_key.\n"
                "  → Get a free key (200 req/day, no card) at https://madeonsol.com/pricing\n\n"
            )
            raise ValueError(
                "Provide api_key. Get a free API key at https://madeonsol.com/pricing"
            )
        if not api_key.startswith("msk_"):
            raise ValueError(
                "api_key must start with 'msk_'. Get one at https://madeonsol.com/pricing"
            )
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"madeonsol-x402-python/{_UA_VERSION}",
        }
        self.last_rate_limit: dict[str, Any] = {
            "limit": None, "remaining": None, "reset": None, "request_id": None,
        }

    def _capture_rate_limit(self, resp: httpx.Response) -> None:
        def _to_int(v: str | None) -> int | None:
            if v is None:
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None
        self.last_rate_limit = {
            "limit":      _to_int(resp.headers.get("x-ratelimit-limit")),
            "remaining":  _to_int(resp.headers.get("x-ratelimit-remaining")),
            "reset":      _to_int(resp.headers.get("x-ratelimit-reset")),
            "request_id": resp.headers.get("x-request-id"),
        }

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Drop unset params. httpx encodes None as an EMPTY value (`?tier=`),
        # which the routes' Zod schemas reject with a 400 rather than treating
        # as "not supplied" — so an omitted keyword argument must never reach
        # the wire. Mirrors ``_clean`` in the robinhood-chain client.
        clean = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        resp = httpx.request(
            method,
            f"{self.base_url}/api/v1{path}",
            headers=self._headers,
            json=json_body,
            params=clean or None,
        )
        self._capture_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    # ── Webhooks ──

    def create_webhook(
        self,
        *,
        url: str,
        events: list[str],
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a webhook. Returns webhook with HMAC secret (shown once)."""
        body: dict[str, Any] = {"url": url, "events": events}
        if filters:
            body["filters"] = filters
        return self._request("POST", "/webhooks", body)

    def list_webhooks(self) -> dict[str, Any]:
        """List all your registered webhooks."""
        return self._request("GET", "/webhooks")

    def get_webhook(self, webhook_id: int) -> dict[str, Any]:
        """Get webhook detail with recent delivery log."""
        return self._request("GET", f"/webhooks/{webhook_id}")

    def update_webhook(self, webhook_id: int, **kwargs: Any) -> dict[str, Any]:
        """Update a webhook (url, events, filters, is_active)."""
        return self._request("PATCH", f"/webhooks/{webhook_id}", kwargs)

    def delete_webhook(self, webhook_id: int) -> dict[str, Any]:
        """Delete a webhook permanently."""
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: int, *, event: str | None = None) -> dict[str, Any]:
        """Send a test payload to verify a webhook URL.

        Args:
            webhook_id: The webhook to test.
            event: Which of the webhook's subscribed events to sample (for
                example 'kol:trade' or 'wallet_tracker:event'). Omit it to
                sample the first subscribed event; an event the webhook is not
                subscribed to is answered with 400.

        Returns ``success``, ``status_code``, ``response_time_ms`` and, on
        servers from 2026-09-25 on, ``event`` (the event type sampled).
        """
        body: dict[str, Any] = {"webhook_id": webhook_id}
        if event is not None:
            body["event"] = event
        return self._request("POST", "/webhooks/test", body)

    # ── Sniper: deshred pre-confirm pump.fun deploys (PRO + ULTRA) ──
    # Reconstructed from shred-level ("deshred") data, deploys surface ~500ms
    # before the chain confirms them. PRO sees elite/good deployers; ULTRA sees
    # every tier and can keep a custom deployer watchlist.

    def sniper_recent(
        self,
        *,
        since: str | None = None,
        deployer_tier: str | None = None,
        min_bond_rate: float | None = None,
        limit: int | None = None,
        watchlist: bool | None = None,
    ) -> dict[str, Any]:
        """Deshred deploy feed — pump.fun launches ~500ms before they confirm.

        PRO sees elite/good deployers; ULTRA sees all tiers. Pass watchlist=True
        (ULTRA) to narrow to your custom deployer watchlist (any tier).

        v1.22 — each deploy carries ``footprint``: the slot-window snipe
        rollup (``buys``, ``buyers``, ``sol``, ``supply_pct``,
        ``sniper_wallet_buys``, ``data_available``, ``as_of``; buys in slots
        deploy-1..deploy+3), or ``None`` for deploys younger than the ~10-min
        settle window or outside the trade-pipeline write-gate — absent, not
        zero.
        """
        params: dict[str, Any] = {}
        if since:
            params["since"] = since
        if deployer_tier:
            params["deployer_tier"] = deployer_tier
        if min_bond_rate is not None:
            params["min_bond_rate"] = min_bond_rate
        if limit is not None:
            params["limit"] = limit
        if watchlist:
            params["watchlist"] = "true"
        return self._request("GET", "/sniper/recent", params=params or None)

    def sniper_by_deployer(self, wallet: str, *, limit: int | None = None) -> dict[str, Any]:
        """Deshred deploys filtered to a single deployer wallet. ULTRA only."""
        params = {"limit": limit} if limit is not None else None
        return self._request("GET", f"/sniper/by-deployer/{wallet}", params=params)

    def sniper_watchlist(self) -> dict[str, Any]:
        """List your custom sniper deployer watchlist (ULTRA, max 50)."""
        return self._request("GET", "/sniper/watchlist")

    def sniper_watchlist_add(
        self,
        *,
        wallet: str | None = None,
        wallets: list[str] | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Add one (wallet) or many (wallets) deployers to your watchlist. ULTRA only."""
        body: dict[str, Any] = {}
        if wallet:
            body["wallet"] = wallet
        if wallets:
            body["wallets"] = wallets
        if label:
            body["label"] = label
        return self._request("POST", "/sniper/watchlist", body)

    def sniper_watchlist_remove(self, wallet: str) -> dict[str, Any]:
        """Remove a deployer from your watchlist. ULTRA only."""
        return self._request("DELETE", f"/sniper/watchlist/{wallet}")

    # ── KOL/deployer detail ──

    def kol_pnl(self, wallet: str, *, period: str = "30d") -> dict[str, Any]:
        """Deep per-wallet PnL: equity curve, risk metrics, positions."""
        return self._request("GET", f"/kol/{wallet}/pnl", params={"period": period})

    def kol_timing(self, wallet: str, *, period: str = "30d") -> dict[str, Any]:
        """KOL entry/exit timing profile — hold duration, exit speed, patterns."""
        return self._request("GET", f"/kol/{wallet}/timing", params={"period": period})

    def deployer_trajectory(self, wallet: str) -> dict[str, Any]:
        """Deployer skill curve — streaks, rolling bond rate, trend."""
        return self._request("GET", f"/deployer-hunter/{wallet}/trajectory")

    def deployer_history(self, wallet: str, limit: int = 90) -> dict[str, Any]:
        """A deployer's daily reputation time-series — backtest "was this
        deployer elite when it launched token X?" without look-ahead bias.

        Returns ``is_deployer``, ``wallet``, and a ``snapshots`` array (each
        entry: ``date``, ``tier``, ``is_tracked``, ``total_deployed``,
        ``total_bonded``, ``bonding_rate``, ``recent_bond_rate``, ``avg_peak_mc``,
        ``best_token_peak_mc``).

        Args:
            wallet: Deployer wallet address.
            limit: Number of daily snapshots to return, 1–365 (default 90).
        """
        return self._request(
            "GET", f"/deployer-hunter/{wallet}/history", params={"limit": limit}
        )

    def deployer_as_of(self, wallet: str, *, date: str | None = None) -> dict[str, Any]:
        """A deployer's reputation exactly as it stood on ``date`` — the latest
        write-on-change snapshot at or before it, so a backtest sees only what
        was knowable then.

        ``snapshot.snapshot_date`` can predate ``date`` (snapshots are
        write-on-change); ``snapshot.carried`` is ``True`` when the state was
        recorded earlier and had not changed by ``date``. No snapshot at or
        before ``date`` returns ``as_of: False, snapshot: None`` — nothing is
        ever synthesized.

        Args:
            wallet: Deployer wallet address.
            date: YYYY-MM-DD (UTC). Default: today. Must be >= 2026-04-07 and
                not in the future.
        """
        params = {"date": date} if date is not None else None
        return self._request(
            "GET", f"/deployer-hunter/{wallet}/as-of", params=params
        )

    def deployer_rewards(self, wallet: str) -> dict[str, Any]:
        """pump.fun creator-fee rewards for a wallet, answered two ways that
        are never merged: ``collected`` (what actually reached the wallet —
        direct vault claims kept 90 days, social-handle claims, shareholder
        payouts on any token) and ``attributed`` (every payout on the tokens it
        deployed, split ``to_self``/``to_others`` + ``redirected_pct``).

        Every money field is ``{sol, usdc, usd}``; ``usd`` is ``None`` (never a
        silent 0) when a SOL amount exists and no SOL price was available.
        Works for non-deployers too (``is_deployer: False``, ``attributed``
        empty).

        Args:
            wallet: Wallet address.
        """
        return self._request("GET", f"/deployer-hunter/{wallet}/rewards")

    # ── Deployer hunter: reputation, leaderboard, outcomes ──
    #
    # "Bonding" is the pump.fun graduation event. ``bonding_rate`` is lifetime,
    # ``recent_bond_rate`` is the rolling recent window — a deployer can carry a
    # strong lifetime rate and a collapsing recent one, which is exactly why
    # both are exposed. ``runner_rate`` is meaningless until
    # ``labeled_tokens >= 3``.

    def deployer_stats(self) -> dict[str, Any]:
        """Ecosystem-wide deployer stats.

        Returns ``tracked_count``, ``signals_today``, ``bonds_detected``,
        the chain-wide ``bond_rate``, and a per-tier ``tiers`` count.

        Route: ``GET /api/v1/deployer-hunter/stats``.
        """
        return self._request("GET", "/deployer-hunter/stats")

    def deployer_leaderboard(
        self,
        *,
        tier: str | None = None,
        sort: str = "bonding_rate",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Deployer reputation leaderboard. Excludes unranked deployers.

        Compare ``bonding_rate`` (lifetime) against ``recent_bond_rate``
        (rolling): the gap between them is the signal, not either alone.

        Args:
            tier: Restrict to one grade (``elite``/``good``/``rising``/…).
            sort: ``'bonding_rate'`` (default) | ``'recent'`` |
                ``'total_bonded'`` | ``'last_deploy'``.
            limit: Page size (1–100, default 20).
            offset: Page offset (default 0).

        Route: ``GET /api/v1/deployer-hunter/leaderboard``.
        """
        return self._request(
            "GET",
            "/deployer-hunter/leaderboard",
            params={"tier": tier, "sort": sort, "limit": limit, "offset": offset},
        )

    def deployer_profile(self, wallet: str) -> dict[str, Any]:
        """One deployer's profile — tier, bond rates, totals, runner rate.

        An untracked wallet returns a profile with zeroed counters, not a 404.
        Gate ``runner_rate`` on ``labeled_tokens >= 3``.

        Args:
            wallet: Deployer wallet address (base58).

        Route: ``GET /api/v1/deployer-hunter/{wallet}``.
        """
        return self._request("GET", f"/deployer-hunter/{wallet}")

    def deployer_tokens(
        self,
        wallet: str,
        *,
        limit: int = 50,
        offset: int = 0,
        only_bonded: bool = False,
    ) -> dict[str, Any]:
        """Every token deployed by one wallet, paginated.

        Each row carries ``deployed_at``, ``bonded_at``, time-to-bond and peak
        market cap.

        Args:
            wallet: Deployer wallet address (base58).
            limit: Page size (1–100, default 50).
            offset: Page offset (default 0).
            only_bonded: Return only tokens that graduated.

        Route: ``GET /api/v1/deployer-hunter/{wallet}/tokens``.
        """
        return self._request(
            "GET",
            f"/deployer-hunter/{wallet}/tokens",
            params={"limit": limit, "offset": offset, "only_bonded": only_bonded},
        )

    def deployer_alert_stats(self, *, period: str | None = None) -> dict[str, Any]:
        """Deployer alert volume over a lookback window.

        Carries bond-rate and MC-multiplier distributions broken out per tier —
        for sizing and monitoring your deployer-hunter usage.

        Args:
            period: Lookback window, e.g. ``'24h'``, ``'7d'``, ``'30d'``.

        Route: ``GET /api/v1/deployer-hunter/alert-stats``.
        """
        return self._request(
            "GET", "/deployer-hunter/alert-stats", params={"period": period}
        )

    def deployer_best_tokens(
        self, *, period: str = "7d", limit: int = 5
    ) -> dict[str, Any]:
        """Best-performing recent tokens from ranked (non-unranked) deployers.

        Args:
            period: Lookback window (default ``'7d'``).
            limit: Rows to return (default 5).

        Route: ``GET /api/v1/deployer-hunter/best-tokens``.
        """
        return self._request(
            "GET", "/deployer-hunter/best-tokens", params={"period": period, "limit": limit}
        )

    def deployer_recent_bonds(
        self,
        *,
        limit: int = 20,
        since: str | None = None,
        tier: str | None = None,
        peak_mc_min: int | None = None,
    ) -> dict[str, Any]:
        """Tokens from tracked deployers that just graduated to Raydium.

        Poll forward: pass the previous response's ``next_since`` back as
        ``since`` to fetch only what bonded after it.

        Args:
            limit: Page size (1–100, default 20).
            since: Incremental cursor from a prior ``next_since``.
            tier: Restrict to one deployer grade.
            peak_mc_min: Floor on peak market cap (USD).

        Route: ``GET /api/v1/deployer-hunter/recent-bonds``.
        """
        return self._request(
            "GET",
            "/deployer-hunter/recent-bonds",
            params={
                "limit": limit,
                "since": since,
                "tier": tier,
                "peak_mc_min": peak_mc_min,
            },
        )

    # ── Streaming ──

    def get_stream_token(self, *, rotate: bool = False) -> dict[str, Any]:
        """Issue your WebSocket streaming token.

        Stream tokens never expire (since 2026-08-27): every call returns the
        same token until your subscription lapses or you pass ``rotate=True``,
        which replaces it (the previous value keeps working for 60 s).
        ``expires_at`` / ``next_refresh_at`` are always ``None`` — the server
        never rotates on its own and never sends ``token_refresh`` unless you
        rotated. The response also carries ``rotated`` (bool) and ``lifetime``
        (str). A ``4001`` close means "mint again" (lapsed or rotated), never a
        timer. Authenticate the handshake with ``Authorization: Bearer <token>``
        (``?token=`` still works, masked in logs).
        """
        return self._request("POST", "/stream/token", {"rotate": True} if rotate else None)

    def stream(
        self, *, auto_reconnect: bool = True, max_backoff: float = 30.0, **stream_options: Any
    ) -> "MadeOnSolStream":
        """Open a managed real-time WebSocket stream — auto-reconnect, token fetch
        (the token does not expire; ``get_stream_token()`` is called on every
        (re)connect), and typed callbacks. Requires the optional ``websockets`` extra::

            pip install "madeonsol-x402[stream]"

        Example::

            stream = client.stream()
            stream.on("kol:trade", lambda d: print(d["token_symbol"]))
            stream.subscribe(["kol:trades"])
            await stream.run()

        ``stream_options`` go to :class:`MadeOnSolStream` — e.g. ``resume=``
        (a cursor you persisted from ``stream.get_cursor()``), ``dedupe_size``,
        ``max_auth_retries``, ``connection_limit_backoff``.
        """
        from .stream import MadeOnSolStream

        async def _token() -> dict[str, Any]:
            return await asyncio.to_thread(self.get_stream_token)

        return MadeOnSolStream(
            _token, auto_reconnect=auto_reconnect, max_backoff=max_backoff, **stream_options
        )

    def stream_sessions(self) -> dict[str, Any]:
        """List your live WebSocket sessions across both stream services (PRO+).

        Returns ``{"sessions": [...], "count": N}``. Each session carries ``id``
        (str), ``service`` ('ws-streaming' | 'dex-stream'), ``tier`` (str),
        ``channels`` (list[str]), ``connected_at`` (ISO 8601), ``remote_ip``
        (str | None), and ``messages_sent`` (int). Reflects live in-memory state
        (not the ws_sessions audit table), so every listed slot is evictable via
        :meth:`kill_stream_session`. PRO/ULTRA only — BASIC callers receive 403.
        """
        return self._request("GET", "/stream/sessions")

    def kill_stream_session(self, session_id: int | str) -> dict[str, Any]:
        """Force-terminate one of your live WebSocket sessions and free its slot.

        Pass a session ``id`` from :meth:`stream_sessions`. Returns
        ``{"evicted": true, "id": ...}`` on success. Self-serve fix for a 4002
        connection-limit lockout when a deploy overlap leaves a ghost socket
        holding your slot. HTTP 404 if no live session with that id exists for
        your key; HTTP 400 if the id is not a positive integer. Scoping is
        enforced server-side — a key can only evict its own sessions. PRO/ULTRA
        only.

        Args:
            session_id: The session id (positive integer) to evict.
        """
        return self._request("DELETE", f"/stream/sessions/{session_id}")

    # ── Account (v1.7) ──

    def me(self) -> dict[str, Any]:
        """Inspect your account: tier, daily/burst quota state, subscription
        expiry, and per-feature usage. Use ``quota['daily']['remaining']`` for
        self-throttling without parsing rate-limit headers.
        ``features['wallet_tracker_watchlist']`` carries ``used`` and, on
        servers from 2026-09-25 on, ``limit`` (the watchlist cap).
        """
        return self._request("GET", "/me")

    # ── Token directory (v1.7, PRO+) ──

    def tokens_list(
        self,
        *,
        min_mc: float | None = None,
        max_mc: float | None = None,
        min_liq: float | None = None,
        active_h: float | None = None,
        primary_dex: str | None = None,
        authority_revoked: bool | None = None,
        exclude_token2022: bool | None = None,
        min_lp_burnt_pct: float | None = None,
        min_volume_1h_usd: float | None = None,
        max_mev_share_pct: float | None = None,
        mc_change_1h_min_pct: float | None = None,
        mc_change_1h_max_pct: float | None = None,
        min_liq_mc_ratio: float | None = None,
        max_liq_mc_ratio: float | None = None,
        deployer_tier: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Filtered, sortable token directory (PRO+).

        Default ``min_liq=2000`` skips phantom-MC dust (low-liq pools with absurd
        VWAP × supply products). Pass ``min_liq=0`` to opt out. Computed filters
        (``min_volume_1h_usd``, ``max_mev_share_pct``, ``mc_change_1h_min_pct``,
        ``mc_change_1h_max_pct``) over-fetch 3× and post-filter in client —
        ``pagination['post_filtered']`` will be ``True`` and page size may be
        smaller than ``limit``.

        Sort values: ``mc_desc`` | ``mc_asc`` | ``last_trade_desc`` |
        ``liquidity_desc`` | ``cumulative_volume_desc`` | ``mc_change_5m_desc`` |
        ``mc_change_1h_desc`` | ``volume_1h_desc`` | ``trending`` (v1.18 — the
        last four are DB-native momentum / trending sorts; ``trending`` is a
        composite recent-volume × positive-momentum rank).

        Primary DEX values: ``pumpfun`` | ``pumpswap`` | ``raydium`` |
        ``meteora`` | ``orca`` | ``raydium_clmm``.

        Args:
            min_liq_mc_ratio: v1.13 — minimum liquidity-to-MC ratio (0-1).
            max_liq_mc_ratio: v1.13 — maximum liquidity-to-MC ratio (0-1).
            deployer_tier: v1.13 — filter by deployer tier: 'elite', 'good',
                'moderate', 'rising', 'cold', or 'unranked'.
            sort: v1.18 — adds momentum sorts 'mc_change_5m_desc',
                'mc_change_1h_desc', 'volume_1h_desc', 'trending'.
        """
        params: dict[str, Any] = {}
        for key, val in {
            "min_mc": min_mc,
            "max_mc": max_mc,
            "min_liq": min_liq,
            "active_h": active_h,
            "primary_dex": primary_dex,
            "authority_revoked": authority_revoked,
            "exclude_token2022": exclude_token2022,
            "min_lp_burnt_pct": min_lp_burnt_pct,
            "min_volume_1h_usd": min_volume_1h_usd,
            "max_mev_share_pct": max_mev_share_pct,
            "mc_change_1h_min_pct": mc_change_1h_min_pct,
            "mc_change_1h_max_pct": mc_change_1h_max_pct,
            "min_liq_mc_ratio": min_liq_mc_ratio,
            "max_liq_mc_ratio": max_liq_mc_ratio,
            "deployer_tier": deployer_tier,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }.items():
            if val is None:
                continue
            params[key] = "true" if val is True else "false" if val is False else val
        return self._request("GET", "/tokens", params=params)

    def almost_bonded(
        self,
        *,
        min_progress: float | None = None,
        max_progress: float | None = None,
        min_velocity_pct_per_min: float | None = None,
        max_age_minutes: float | None = None,
        deployer_tier: str | None = None,
        authority_revoked: bool | None = None,
        min_liq: float | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """v1.18 — Pre-bond pump.fun tokens approaching graduation (PRO+).

        Ranked by velocity (Δprogress/min) — "95% and accelerating" beats
        "92% stalled". Each token is enriched with its deployer's reputation
        tier. ``progress_pct`` comes from on-chain ``real_token_reserves``
        depletion; ``velocity_pct_per_min`` is ``None`` until a 5m snapshot
        exists; ``eta_minutes`` is a linear projection.

        Returns a dict with ``tokens`` (each with ``mint``, ``symbol``,
        ``name``, ``progress_pct``, ``velocity_pct_per_min``, ``eta_minutes``,
        ``stalled``, ``real_sol_reserves``, ``market_cap_usd``,
        ``liquidity_usd``, ``authorities_revoked``, ``deployer_tier``,
        ``age_minutes``), ``filters``, ``returned``, and ``note``.

        Args:
            min_progress: Lower bound on bonding progress % (default 80).
            max_progress: Upper bound on bonding progress % (default 99.99 —
                already-bonded excluded).
            min_velocity_pct_per_min: Minimum Δprogress/min. Tokens without a
                5m-ago snapshot are dropped when set.
            max_age_minutes: Max minutes since deploy (post-filter).
            deployer_tier: 'elite', 'good', 'moderate', 'rising', 'cold', or
                'unranked'.
            authority_revoked: Only tokens with mint+freeze authorities revoked.
            min_liq: Minimum liquidity USD.
            sort: 'velocity_desc' (default), 'progress_desc', or 'eta_asc'.
            limit: Page size (1-100, default 50).
        """
        params: dict[str, Any] = {}
        for key, val in {
            "min_progress": min_progress,
            "max_progress": max_progress,
            "min_velocity_pct_per_min": min_velocity_pct_per_min,
            "max_age_minutes": max_age_minutes,
            "deployer_tier": deployer_tier,
            "authority_revoked": authority_revoked,
            "min_liq": min_liq,
            "sort": sort,
            "limit": limit,
        }.items():
            if val is None:
                continue
            params[key] = "true" if val is True else "false" if val is False else val
        return self._request("GET", "/tokens/almost-bonded", params=params)

    # ── Alpha Wallet Intelligence ──

    def alpha_leaderboard(
        self,
        *,
        period: str = "30d",
        min_tokens: int = 5,
        sort: str = "win_rate",
        exclude_bots: bool = True,
    ) -> dict[str, Any]:
        """Top statistically profitable early-buyer wallets.

        Args:
            period: '7d', '30d', or 'all'.
            min_tokens: 1–20 — minimum tokens traded by the wallet.
            sort: 'win_rate', 'pnl', or 'roi'.
            exclude_bots: Exclude wallets flagged as bots.

        BASIC: 25 results, truncated wallets, rounded values.
        PRO: 100 results, full wallets + extended stats.
        ULTRA: 500 results + bot_confidence + behavioral signals.
        """
        return self._request("GET", "/alpha/leaderboard", params={
            "period": period,
            "min_tokens": min_tokens,
            "sort": sort,
            "exclude_bots": "true" if exclude_bots else "false",
        })

    def alpha_wallet(self, wallet: str) -> dict[str, Any]:
        """Full alpha profile for one wallet — per-token breakdown + bot signals.

        ULTRA only.
        """
        return self._request("GET", f"/alpha/{wallet}")

    def alpha_linked(self, wallet: str) -> dict[str, Any]:
        """Wallets behaviorally linked to this one (co-bought 3+ tokens within 2s).

        ULTRA only.
        """
        return self._request("GET", f"/alpha/{wallet}/linked")

    # ── Token Quality ──

    def token_cap_table(self, mint: str) -> dict[str, Any]:
        """First non-deployer early buyers for a token, enriched with PnL/KOL/bot flags.

        BASIC: 403. PRO: top 10, truncated wallets. ULTRA: top 20, full wallets.
        """
        return self._request("GET", f"/tokens/{mint}/cap-table")

    def token_buyer_quality(self, mint: str) -> dict[str, Any]:
        """0–100 buyer-quality score for a token's first-buyer cohort.

        BASIC: score + signal only. PRO/ULTRA: full breakdown.
        Cached for 5 minutes per mint.
        """
        return self._request("GET", f"/tokens/{mint}/buyer-quality")

    def token_risk(self, mint: str) -> dict[str, Any]:
        """Transparent 0–100 token rug-risk/safety score (higher = riskier).

        Returns ``risk_score``, a ``band`` ('safe' | 'caution' | 'danger'), an
        explainable ``factors`` array, and the raw ``inputs`` (mint/freeze
        authority, liquidity, liq-to-MC ratio, transfer fee, launch cohort,
        deployer bond rate, KOL signal, blacklist). PRO/ULTRA only — BASIC
        callers receive HTTP 403.

        v1.22 — ``inputs`` gains ``sniper_footprint``: the slot-window
        launch-snipe rollup (``buys``, ``buyers``, ``sol``, ``supply_pct``,
        ``sniper_wallet_buys``, ``data_available``, ``as_of``). ``None`` = no
        rollup; ``data_available=False`` = not observable, NOT zero snipes.

        v1.23 — the response gains a top-level ``dev`` object (deployer
        self-activity: ``wallet``, ``launchpad``, ``deployed_at``, ``buy_sol``,
        ``buy_tokens``, ``buy_supply_pct``, ``bought_tokens_after``,
        ``sold_tokens``, ``sold_sol``, ``first_sell_at``, ``last_sell_at``,
        live ``holdings_tokens`` / ``holdings_supply_pct``, ``wallet_empty``,
        ``transfer_status`` -- suspected / none_detected / unknown; ``transferred_out``
        is its deprecated boolean view) plus ``as_of``. ``dev`` is ``None`` when the mint
        has no tracked deploy row. Score v2 (2026-09-21): ``assessment`` lists
        ``unknown_inputs`` / ``not_assessed``; a token-supply burn is never LP evidence;
        a failed score-critical read is HTTP 503 ``risk_inputs_unavailable``.

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/risk")

    def token_bundle(self, mint: str) -> dict[str, Any]:
        """Bundle-cohort holdings — how much of a token's supply the launch
        bundle still holds.

        Returns a ``bundle`` summary (``wallet_count``, ``bundle_kind``
        ('atomic_tx' | 'same_slot' | 'none'), ``held_ratio`` net-held /
        buy-volume — churn-sensitive, secondary, ``held_pct_of_supply``
        net-held / circulating supply — the HEADLINE signal, ``None`` when
        supply is unknown, ``fully_exited``, ``buy_volume`` cumulative buy
        volume (NOT distinct tokens — can exceed supply), and ``tokens_held``
        swap-derived net position) plus a ``wallets`` array. All tiers reach
        the endpoint; the response is field-gated by tier: BASIC get
        the ``bundle`` summary only (``wallets`` is empty), PRO adds the top-10
        wallets with flags only (``rank``, ``wallet``, ``held_ratio``,
        ``has_sold``, ``atomic``, ``is_kol``), and ULTRA adds per-wallet
        identity (``kol_name``, ``win_rate``, ``bot_confidence``,
        ``tokens_held``).

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/bundle")

    def token_pools(self, mint: str) -> dict[str, Any]:
        """Per-venue liquidity map — every DEX pool a token trades in, live vs
        parked, fragmentation + top-pool share.

        Returns ``mint`` and a ``pools`` array (each entry: ``pool_address``,
        ``dex``, ``quote_mint``, ``liquidity_usd``, ``last_price_sol``,
        ``last_swap_at``, ``amm_id``, ``is_active``) plus a ``summary``
        (``pool_count``, ``active_pool_count``, ``dex_count``, ``dexes``,
        ``total_liquidity_usd``, ``primary_pool``, ``primary_dex``,
        ``top_pool_share_pct``). PRO/ULTRA only — BASIC callers receive HTTP 403.

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/pools")

    def token_holders(self, mint: str) -> dict[str, Any]:
        """Live holder census + concentration for a token — who holds NOW (PRO+).

        Read live from the ledger at ``confirmed``: every token account of the
        mint (mint-scoped ``getProgramAccounts``), merged per owner. Returns
        ``mint``, ``slot``, ``as_of``, a ranked ``holders`` array, ``count``,
        ``disclosed``, ``excluded``, ``concentration``, ``deployer`` and
        ``source``.

        Hard truths the payload states rather than hides:

        * ``concentration.holder_count`` is EXACT (distinct non-zero owners
          minus the excluded pools / curves / burns) via the census. It is
          ``None`` ONLY when the provider refuses the census for a mega-cap
          (TRUMP/JUP/BONK class) — then ``source.method`` is
          ``'getTokenLargestAccounts'``, ``source.census_fallback_reason`` is
          set and only the top-20 view is served. It is never estimated from
          trades.
        * Every disclosed owner carries ``labels`` from MadeOnSol wallet
          intelligence: ``deployer`` / ``kol`` / ``early_buyer`` / ``buyer`` /
          ``bundle`` / ``bot`` / ``dump_cluster`` (+ ``kol_name``,
          ``early_buyer_rank``, ``bot_confidence``, ``historical_win_rate``).
          An empty ``labels`` list means unknown to us — NOT verified clean.
        * Liquidity pools, bonding curves, vaults and burn addresses are
          EXCLUDED from the circulating denominator and NAMED in ``excluded[]``
          — ``reason`` is ``'pool'`` (+ ``dex``, ``pool_address``),
          ``'bonding_curve'`` (pump.fun / LaunchLab), ``'burn'`` or
          ``'program_account'`` (an off-curve owner we could not attribute).
          ``concentration`` splits them into ``pool_pct`` / ``burned_pct`` /
          ``program_pct`` (over TOTAL supply); ``top1/10/20/50/100_share`` and
          the ``deployer/kol/early_buyer/bundle/bot/dump_cluster_pct`` are over
          circulating (supply minus excluded).
        * ``amount_raw``, ``supply_raw`` and ``circulating_raw`` are raw u64
          values returned as STRINGS — never floats. ``amount`` is the
          decimal-adjusted convenience float.
        * Disclosure depth is tier-gated (PRO ranks 1–10, ULTRA 1–50,
          BUSINESS 1–100); the concentration maths is tier-independent.

        Large established tokens take 5–30 s to enumerate upstream: the first
        call may raise ``httpx.HTTPStatusError`` with HTTP 503 and body
        ``error_kind='holder_scan_in_progress'`` / ``retry_after_seconds=20``.
        The scan keeps running and is cached, so retrying after ~20 s is
        instant. HTTP 404 ``error_kind='not_a_mint'`` = not a mint on-chain;
        503 ``holder_rpc_unavailable`` (retry 15 s) = fail-closed, never a
        trade-derived guess. Distinct from :meth:`token_cap_table` (who bought
        first) — this is who holds now. Not on the keyless x402 rail.

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/holders")

    def token_locks(
        self,
        mint: str,
        *,
        status: str | None = None,
        program: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Token locks & vesting on a mint — Streamflow, Jupiter Lock, Bonfida
        vesting (PRO+). *Did the team lock, how much, until when, and can they
        pull it?*

        Every on-chain lock / vesting contract on the mint, decoded from the
        locker programs' account state, each with the schedule (``start_at``,
        ``cliff_at``, ``end_at``, ``period_seconds``, ``cliff_amount_raw``,
        ``amount_per_period_raw``), the terms (``cancelable_by_sender``,
        ``cancelable_by_recipient``, ``transferable``, ``can_topup``) and a
        live-derived view computed at request time: ``locked_raw`` (still locked
        now), ``unlocked_raw``, ``withdrawn_raw``, ``claimable_raw``, ``status``
        (``active`` | ``completed`` | ``cancelled`` | ``closed``) and
        ``next_unlock`` (``cliff`` | ``period`` | ``final`` | ``tranche``).
        ``summary`` rolls up ``lock_count`` (exact), ``active_count``,
        ``by_program`` / ``by_kind``, ``distinct_lockers``, locked / deposited
        totals (raw + ui + usd + ``_pct_of_supply``), the ``unlocking_7d_*`` /
        ``unlocking_30d_*`` forward schedule, the nearest ``next_unlock`` and
        ``active_cancelable_by_sender`` (funds are locked against the
        *recipient*, not the locker — a cancelable lock is a weaker promise).
        ``summary.complete`` is ``False`` when the mint holds > 5000 contracts
        (totals then cover the newest 5000, ``rows_considered``).

        Amounts (``*_raw``) are base-unit digit STRINGS; ``amount`` /
        ``*_usd`` / ``*_pct_of_supply`` are ``None`` when decimals or price are
        unknown (see ``token.facts_resolved``). **LP locks are NOT included**
        — this is token / vesting locks only. Keyed (``msk_``) API only, not on
        the x402 rail; BASIC gets HTTP 403.

        Args:
            mint: Token mint address.
            status: Filter the list — 'active' | 'completed' | 'cancelled' | 'closed'
                (the summary always covers all rows).
            program: 'streamflow' | 'jupiter_lock' | 'bonfida_vesting'.
            limit: 1–500, default 200.

        Route: ``GET /api/v1/tokens/{mint}/locks``.
        """
        return self._request(
            "GET",
            f"/tokens/{mint}/locks",
            params={"status": status, "program": program, "limit": limit},
        )

    def token_locks_feed(
        self,
        *,
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
    ) -> dict[str, Any]:
        """Cross-token feed of NEW lock / vesting contracts, newest first (PRO+)
        — who just locked tokens, of what mint, how much, until when.

        Same row shape as :meth:`token_locks` rows plus a per-row ``token``
        block (``symbol``, ``name``, ``decimals``, ``price_usd``,
        ``market_cap_usd``). Poll forward with ``since=`` (cursor =
        ``pagination.next_since``), page back with ``before=`` (cursor =
        ``pagination.next_before``), or subscribe to the ``token:locks``
        WebSocket channel (event ``token:lock``, pushed the moment the contract
        lands on-chain) — the response carries a ``stream`` pointer.
        ``min_usd`` / ``min_pct_of_supply`` / ``status`` post-filter with a ×4
        over-fetch. Backfilled Jupiter Lock rows have no on-chain creation time
        (``created_at_estimated``) and are excluded unless
        ``include_estimated=True``. LP locks are not included. Keyed API only.

        Args:
            since: ISO 8601 — only contracts created after this instant.
            before: ISO 8601 — only contracts created before this instant.
            mint: Filter to one mint.
            sender: Creator / locker wallet.
            recipient: Recipient wallet.
            program: 'streamflow' | 'jupiter_lock' | 'bonfida_vesting'.
            kind: 'lock' | 'vesting'.
            status: 'active' | 'completed' | 'cancelled' | 'closed'.
            min_usd: Deposited amount >= (needs a known price).
            min_pct_of_supply: 0–100.
            include_estimated: Include backfilled Jupiter rows.
            limit: 1–100, default 50.

        Route: ``GET /api/v1/tokens/locks``.
        """
        return self._request(
            "GET",
            "/tokens/locks",
            params={
                "since": since,
                "before": before,
                "mint": mint,
                "sender": sender,
                "recipient": recipient,
                "program": program,
                "kind": kind,
                "status": status,
                "min_usd": min_usd,
                "min_pct_of_supply": min_pct_of_supply,
                "include_estimated": (
                    None if include_estimated is None else ("1" if include_estimated else "0")
                ),
                "limit": limit,
            },
        )

    def token_unlocks(
        self,
        *,
        within: str | None = None,
        mint: str | None = None,
        program: str | None = None,
        kind: str | None = None,
        min_usd: float | None = None,
        min_pct_of_supply: float | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Upcoming token unlock EVENTS across all active lock / vesting
        contracts inside a window (PRO+) — which locked supply hits the market
        this week, how much, from whose lock.

        One entry per active contract = its NEXT unlock event in the window
        (``event`` = ``cliff`` | ``period`` | ``final`` | ``tranche``,
        ``unlock_at``, ``in_seconds``, ``amount_raw`` / ``amount`` /
        ``amount_usd`` / ``amount_pct_of_supply``) plus ``window_amount_*`` =
        that contract's total release over the whole window, the ``token``
        block and the ``lock`` it belongs to (subset of a
        :meth:`token_locks` row). Continuous per-second streams (Streamflow
        payroll) contribute only their cliff / final events. Response:
        ``{window: {within, from, to}, unlocks[], pagination: {limit, count,
        total_in_window, has_more}}``. Amounts are base-unit strings; ui / usd
        / pct are ``None`` when unknown. LP locks not included. Keyed API only.

        Args:
            within: '1h' | '6h' | '24h' | '3d' | '7d' (default) | '14d' | '30d' | '90d'.
            mint: Filter to one mint.
            program: 'streamflow' | 'jupiter_lock' | 'bonfida_vesting'.
            kind: 'lock' | 'vesting'.
            min_usd: Next-event amount >= (needs a known price).
            min_pct_of_supply: 0–100.
            sort: 'soonest' (default) | 'largest_usd' | 'largest_pct'.
            limit: 1–200, default 50.

        Route: ``GET /api/v1/tokens/unlocks``.
        """
        return self._request(
            "GET",
            "/tokens/unlocks",
            params={
                "within": within,
                "mint": mint,
                "program": program,
                "kind": kind,
                "min_usd": min_usd,
                "min_pct_of_supply": min_pct_of_supply,
                "sort": sort,
                "limit": limit,
            },
        )

    def token_fee_shares(self, mint: str) -> dict[str, Any]:
        """pump.fun creator-fee sharing on a mint — who the creator fees are
        redirected to (PRO+).

        The on-chain ``SharingConfig`` of a pump.fun coin (pump_fees PDA
        ``['sharing-config', mint]``): ``config`` with ``admin``, ``status``,
        ``is_default`` (``True`` = 100% to the creator — a real answer, not a
        miss), ``redirected_bps`` / ``redirected_pct`` (share going to
        non-admin addresses), ``social_bps`` / ``social_pct`` and each
        ``shareholders[]`` entry's ``share_bps``, ``is_admin``,
        ``is_social_pda`` (fees earmarked for a platform identity such as an X
        account — ``social.platform`` 2 = X, ``social.user_id`` is the
        platform-native numeric id, not the handle, plus lifetime claimed) and
        what that recipient has ``received`` so far. ``config.source`` is
        ``'stream'`` (our table — only non-default splits are stored) or
        ``'chain'`` (live PDA read; ``config_error`` set and ``config`` None if
        every RPC endpoint failed). ``distributions`` rolls up every
        ``distribute_creator_fees`` payout (count / total / per-recipient
        received, ``past_recipients`` no longer in the split),
        ``history`` is the config change log (created / updated / reset /
        creator transferred, newest first) and ``recent_distributions`` the
        latest payouts. Amounts are quote base-unit STRINGS (SOL lamports
        unless a stable-quoted coin); ui / usd may be ``None``. **Event
        history starts 2026-08-17.** Keyed API only.

        Args:
            mint: pump.fun coin mint address.

        Route: ``GET /api/v1/tokens/{mint}/fee-shares``.
        """
        return self._request("GET", f"/tokens/{mint}/fee-shares")

    def token_fee_claims(
        self,
        *,
        type: str | list[str] | None = None,
        mint: str | None = None,
        recipient: str | None = None,
        actor: str | None = None,
        social_platform: int | None = None,
        social_user_id: str | None = None,
        min_sol: float | None = None,
        since: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """pump.fun fee-event feed, newest first (PRO+): distributions to
        shareholders, social-handle claims and SharingConfig changes.

        ``events[]`` types: ``distribution`` (creator fees paid pro-rata to the
        SharingConfig shareholders, with ``payouts[]`` per address),
        ``social_claim`` (fees earmarked for a platform identity — ``social``
        with ``platform`` 2 = X, ``user_id`` = platform-native numeric id —
        claimed to a ``recipient`` wallet), ``shares_created`` /
        ``shares_updated`` / ``shares_reset``, ``creator_transferred`` and
        ``creator_claim`` (the plain creator vault claim — per creator, no
        ``mint``; EXCLUDED unless requested via ``type``). Each event: ``id``,
        ``type``, ``at``, ``tx_signature``, ``slot``, ``mint`` (``None`` for
        social / creator claims), ``admin``, ``actor``, ``recipient``,
        ``amount_raw`` (quote base-unit STRING), ``amount``, ``amount_usd``,
        ``quote``, ``social``, ``shareholders``, ``payouts``, ``payload``.
        Default 100%-to-creator configs and zero-amount distributions are not
        stored. Poll forward with ``since=`` (cursor = ``pagination.next_since``)
        or subscribe to the ``token:fee_claims`` WebSocket channel (event
        ``token:fee_claim``) — the response carries a ``stream`` pointer.
        **History starts 2026-08-17.** Keyed API only.

        Args:
            type: Event type or list/comma list of types (default: all except
                'creator_claim').
            mint: Filter to one mint.
            recipient: Payout / claim recipient wallet, or new creator.
            actor: Transaction signer.
            social_platform: Raw platform id (2 = X).
            social_user_id: Platform-native numeric user id.
            min_sol: Amount floor in SOL.
            since: ISO 8601 cursor (from ``pagination.next_since``).
            before: ISO 8601 — page back.
            limit: 1–100, default 50.

        Route: ``GET /api/v1/tokens/fee-claims``.
        """
        return self._request(
            "GET",
            "/tokens/fee-claims",
            params={
                "type": ",".join(type) if isinstance(type, (list, tuple)) else type,
                "mint": mint,
                "recipient": recipient,
                "actor": actor,
                "social_platform": social_platform,
                "social_user_id": social_user_id,
                "min_sol": min_sol,
                "since": since,
                "before": before,
                "limit": limit,
            },
        )

    def tokens_surges(
        self,
        *,
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
        exclude_flags: str | list[str] | None = None,
        only_clean: bool | None = None,
        stats: bool | None = None,
        days: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Token surges & revivals — token momentum fires, newest first (PRO+).

        Two kinds share one row shape. ``surge``: a token < 30 min old whose
        market cap runs hard against its LAUNCH MC, in three tiers that each
        fire at most once per mint (tiers are independent — a token can go
        straight to breakout): ``early`` (<=10 min, >=$12k, >=3x launch),
        ``strong`` (<=30 min, >=$30k, >=6x launch AND >=2x the lowest sample of
        the last 3 min — it is climbing now), ``breakout`` (<=2 min, >=$45k,
        >=8x). A tier must be SUSTAINED on the current tick and on a sample
        >=10 s older, and nothing fires before 20 s of age — a one-tick mark
        (same-slot bundle, routed dust) is a spike, not a surge. ``revival``:
        a token with no 1-minute trade candle for >=24 h that starts trading
        again, confirmed ONLY by the tape (>=5 buys, >=$500 buy volume, MC
        >=1.5x the pre-dormancy close, or >=20 buys / >=$5k regardless), never
        by the price mark; ``tier`` is ``None``. Hard gates on both: liquidity
        >=$1.5k and >=2% of MC when known, MC <=$100B, and the MC gained must be
        PAID FOR by buy volume on the tape (a price mark in a spoof pool moves
        MC on ~$0).

        Every row carries the burst ``tape`` (buys / sells / volume;
        ``unique_buyers`` only where the mint is in trade coverage —
        ``wallet_data_available`` False otherwise, never an inferred zero;
        ``source`` says ``candles`` vs ``wallet_trades``, ``available`` False =
        no tape yet), ``kol`` (tracked-KOL buyers + names), ``early_buyers``
        (first-20 cohort: bundled, sold, sniper wallets), ``deployer``
        reputation and ``risk_flags`` — the honest half: ``bundled_launch``,
        ``few_buyers``, ``wash_pattern``, ``thin_liquidity``, ``cold_deployer``,
        ``sniper_heavy``, ``early_buyers_exiting``, ``sell_pressure``,
        ``no_tape_trades``, ``no_prior_price``, ``mint_authority_active``,
        ``transfer_fee`` (thresholds echoed in ``definitions.risk_flags``; an
        empty list is "no flag raised", not "verified clean"). Rows >=65 min
        old carry the +1 h ``outcome`` (``mc_1h_multiple``,
        ``peak_1h_multiple``; ``priced_after_1h`` False = the token stopped
        being priced, not zero). ``stats=True`` adds per-(kind, tier)
        hit-rates over ``days`` (``up_1h_pct``, ``median_peak_multiple``,
        ``doubled_1h_pct``) — out-of-sample by construction, the fire is
        recorded before the outcome exists. Poll forward with ``since=``
        (cursor ``pagination.next_since``), page back with ``before=``, or
        subscribe to the ``token:surges`` WebSocket channel (events
        ``token:surge`` / ``token:revival``, same object minus ``outcome``) —
        the response carries a ``stream`` pointer and echoes the live
        thresholds in ``definitions``. Retention 60 days. Keyed (``msk_``) API
        only, not on the x402 rail; BASIC gets HTTP 403.

        Args:
            kind: 'surge' | 'revival'.
            tier: 'early' | 'strong' | 'breakout' (surge only — 400 with kind='revival').
            mint: Filter to one mint.
            since: ISO 8601 — only fires after this instant (from ``pagination.next_since``).
            before: ISO 8601 — page back (from ``pagination.next_before``).
            min_mc_usd: Market cap at fire time >=.
            max_mc_usd: Market cap at fire time <=.
            min_buys: Tape buys at fire time >=.
            launchpad: Venue at birth, e.g. 'pumpfun' | 'launchlab' | 'bags'.
            deployer_tier: 'elite' | 'good' | 'moderate' | 'rising' | 'cold' | 'unranked'.
            exclude_flags: Risk flag or list/comma list — rows carrying ANY are
                dropped (unknown flag → 400 with ``known_flags``).
            only_clean: Only rows with no risk flags at all.
            stats: Include per-(kind, tier) hit-rates over ``days``.
            days: Stats window, 1–30 (default 7).
            limit: 1–200, default 50.

        Route: ``GET /api/v1/tokens/surges``.
        """
        return self._request(
            "GET",
            "/tokens/surges",
            params={
                "kind": kind,
                "tier": tier,
                "mint": mint,
                "since": since,
                "before": before,
                "min_mc_usd": min_mc_usd,
                "max_mc_usd": max_mc_usd,
                "min_buys": min_buys,
                "launchpad": launchpad,
                "deployer_tier": deployer_tier,
                "exclude_flags": (
                    ",".join(exclude_flags) if isinstance(exclude_flags, (list, tuple)) else exclude_flags
                ),
                "only_clean": None if only_clean is None else ("1" if only_clean else "0"),
                "stats": None if stats is None else ("1" if stats else "0"),
                "days": days,
                "limit": limit,
            },
        )

    def tokens_batch_risk(self, mints: list[str]) -> dict[str, Any]:
        """Bulk token rug-risk/safety scoring — up to 50 mints in one call (PRO+).

        Scores 1–50 base58 mints in a single request that counts as 1 request
        against quota. Returns ``{"tokens": [...], "count": N}`` where each
        ``tokens`` entry mirrors the single-mint :meth:`token_risk` shape
        (``risk_score``, ``band``, explainable ``factors``, raw ``inputs``) plus
        an ``as_of`` ISO-8601 timestamp. Untracked mints come back as
        ``{"mint": ..., "error": "not_tracked"}`` (a per-mint failure may instead
        be ``{"mint": ..., "error": "error"}``) and do NOT fail the batch.
        ``tokens`` preserves de-duplicated input order; ``count`` is the number of
        unique mints. PRO/ULTRA only — BASIC callers receive HTTP 403.

        Args:
            mints: 1–50 base58 token mint addresses. Duplicates are removed.
        """
        return self._request("POST", "/tokens/batch/risk", {"mints": mints})

    def token_batch(self, mints: list[str]) -> dict[str, Any]:
        """Bulk token snapshot for up to 50 mints, cheaper than N sequential
        :meth:`token` calls (all tiers).

        Returns the same per-mint shape as :meth:`token` (MC, holders,
        velocity, MEV-share, history age) for every mint, batched into one
        request. ULTRA callers additionally get wallet addresses inside each
        mint's ``kol_activity.top_buyers``.

        Args:
            mints: 1–50 base58 token mint addresses. Duplicates are removed.
        """
        return self._request("POST", "/token/batch", {"mints": mints})

    def tokens_batch_buyer_quality(self, mints: list[str]) -> dict[str, Any]:
        """Bulk 0-100 buyer-quality scoring for up to 50 mints in one call.

        Same per-mint shape as :meth:`token_buyer_quality`, batched into a
        single request that counts as 1 request against quota.

        Args:
            mints: 1–50 base58 token mint addresses. Duplicates are removed.
        """
        return self._request("POST", "/tokens/batch/buyer-quality", {"mints": mints})

    def token_candles(
        self,
        mint: str,
        *,
        tf: str = "1h",
        limit: int = 200,
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, Any]:
        """1-minute-derived OHLCV candles for a token, aggregated to a timeframe.

        Returns ``mint``, ``timeframe``, ``from``, ``to``, ``count``,
        ``net_flow_included``, and a ``candles`` array. Each candle has ``t``
        (bucket start), ``open``, ``high``, ``low``, ``close``, ``volume_usd``,
        ``trades``, and ``market_cap_usd``. ULTRA additionally exposes per-candle
        net-flow fields: ``buy_volume_usd``, ``sell_volume_usd``,
        ``net_volume_usd``, ``buy_count``, ``sell_count``, ``volume_mev_usd``,
        ``open_liquidity_usd``, ``close_liquidity_usd``, ``high_mc_usd``, and
        ``low_mc_usd``. PRO returns OHLCV over the last 30 days; ULTRA adds the
        net-flow breakdown and full history.

        Args:
            mint: Token mint address.
            tf: Timeframe bucket — '1m', '5m', '15m', '1h', '4h', or '1d'
                (default '1h').
            limit: Number of candles to return, 1–1000 (default 200).
            from_: Optional ISO8601 start timestamp (maps to the ``from`` query
                param; ``from`` is reserved in Python).
            to: Optional ISO8601 end timestamp.
        """
        params: dict[str, Any] = {"tf": tf, "limit": limit}
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        return self._request("GET", f"/tokens/{mint}/candles", params=params)

    def token_trades(
        self,
        mint: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        action: str | None = None,
        wallet: str | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> dict[str, Any]:
        """v1.22 — Mint-scoped trade tape: cursor-paginated raw trades for one
        token, newest first (the backfill complement to the live DEX firehose).
        PRO+.

        Each trade: ``tx_signature``, ``wallet_address``, ``action``
        (``'buy'`` | ``'sell'``), ``sol_amount``, ``token_amount``,
        ``price_sol`` (``float | None``), ``price_usd`` (``float | None``),
        ``market_price_sol`` (``float | None``), ``market_price_usd``
        (``float | None``), ``early_buyer_rank`` (``int | None``), ``slot`` (``int | None``),
        ``block_time`` (unix sec), ``traded_at`` (ISO 8601). The response also
        carries ``next_cursor``, ``has_more``, ``filters``, and a ``coverage``
        honesty block (``history_start``, ``scope``) — capture starts
        2026-04-12 and is pump.fun-pipeline scoped.

        Two prices, on purpose. ``price_sol``/``price_usd`` are THIS trade's
        executed price — ``sol_amount / token_amount``, so they reconcile exactly
        with the amounts on the same row and with the PnL endpoints. Since
        ``sol_amount`` is the wallet's net SOL movement, that is the trader's
        all-in effective rate: it includes the swap fee and any account rent paid
        in the same transaction, and it is not the pool mid.
        ``market_price_sol``/``market_price_usd`` are the market-cap tracker's
        canonical pool price sampled near that trade's slot — one value per token
        per update, shared by every trade in the slot. Use the first pair for cost
        basis, fills and PnL; the second for a per-token price series independent
        of trade size and direction. (Before 2026-08-16 ``price_sol`` carried the
        canonical value and disagreed with the row's own amounts by a 7.9% median.)

        Args:
            mint: Token mint address.
            limit: 1-500, default 100.
            cursor: From ``next_cursor`` of a previous response.
            action: 'buy' or 'sell' filter.
            wallet: Filter to a single wallet address.
            since: Unix epoch seconds (default: full history).
            until: Unix epoch seconds (default: now).
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if action is not None:
            params["action"] = action
        if wallet is not None:
            params["wallet"] = wallet
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        return self._request("GET", f"/tokens/{mint}/trades", params=params)

    def token_depth(
        self,
        mint: str,
        *,
        sizes: str | list[float] | None = None,
    ) -> dict[str, Any]:
        """v1.23 — Per-pool price-impact / slippage depth: "how much SOL does it
        take to move the price N%", per pool. PRO+.

        Returns ``mint``, ``found``, ``sol_usd``, ``sizes_sol``,
        ``primary_pool`` (deepest depth-computable pool), a ``pools`` array,
        an ``unsupported_pools`` array, and a ``note``. Each supported pool
        carries ``pool_address``, ``dex``, ``quote_mint``, ``pool_model``,
        ``liquidity_usd``, ``is_active``, ``depth_available`` (always
        ``True``), ``model``, ``fee_pct``, ``source`` (``'stream'`` |
        ``'live_rpc'``), ``reserves_age_ms``, ``spot_price_sol``, per-size
        ``quotes`` (``size_sol``, ``tokens_out``, ``avg_price_sol``,
        ``price_impact_pct``), and ``to_move_price`` (SOL required to move the
        price ``'1pct'`` / ``'5pct'`` / ``'10pct'``). Constant-product AMMs are
        served from stream reserves (zero-RPC); pump.fun/bonk curves from one
        live read of the curve's VIRTUAL reserves. Concentrated pools
        (CLMM/Orca/DLMM), Meteora-DBC curves, and unclassified pools land in
        ``unsupported_pools`` with a ``reason`` rather than a wrong number.
        When no pools are tracked: ``found=False`` with empty arrays.

        Args:
            mint: Token mint address.
            sizes: SOL buy sizes to quote — a CSV string (``"0.5,1,5,10"``) or
                a list of floats. Max 8 values, each > 0 and <= 10000.
                Default 0.5, 1, 5, 10.
        """
        params: dict[str, Any] = {}
        if sizes is not None:
            params["sizes"] = (
                ",".join(str(s) for s in sizes) if isinstance(sizes, list) else sizes
            )
        return self._request("GET", f"/tokens/{mint}/depth", params=params or None)

    # ── Copy-Trade (PRO+) ──

    def copy_trade_list(self) -> dict[str, Any]:
        """List your copy-trade rules."""
        return self._request("GET", "/copytrade/subscriptions")

    def copy_trade_create(
        self,
        *,
        source_wallets: list[str],
        sizing_amount: float,
        name: str | None = None,
        min_trade_sol: float | None = None,
        only_action: str | None = None,
        sizing_mode: str | None = None,
        delivery_mode: str | None = None,
        webhook_url: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Create a copy-trade rule. Returns webhook_secret ONCE — store it.

        Signals fire only for trades by wallets MadeOnSol tracks as KOLs (the
        roster at ``GET /api/v1/kol/wallets``). Any valid Solana address is
        accepted into a rule, but an untracked wallet never produces a signal.
        On servers from 2026-09-25 on the response says which: the
        subscription carries ``source_wallets_tracked`` /
        ``source_wallets_untracked`` and ``warnings`` lists
        ``untracked_source_wallets`` (or ``source_wallet_tracking_unavailable``).

        Args:
            source_wallets: Tracked KOL wallets to follow. The per-rule limit is
                set by your tier and enforced by the server: PRO 5, ULTRA 50,
                BUSINESS 250 (Enterprise follows Business).
            sizing_amount: SOL when sizing_mode is 'fixed'; otherwise a
                multiplier / fraction of the source size (0.25 = a quarter),
                never a percent.
            name: Optional human label.
            min_trade_sol: Minimum source-wallet trade size to fire a signal.
            only_action: 'buy', 'sell', or 'both'. When omitted the server
                default 'buy' applies.
            sizing_mode: 'fixed' (default), 'proportional' or 'percent_source'
                (the last two are the same maths: source size × sizing_amount).
            delivery_mode: 'webhook', 'websocket', or 'both'.
            webhook_url: Required when delivery_mode includes 'webhook'.
            min_mc_usd: Lower bound (USD, 0 to 1e12) on the source trade's
                market cap at trade time. When a bound is set, trades with an
                unknown market cap are dropped.
            max_mc_usd: Upper bound (USD, 0 to 1e12); must be >= min_mc_usd.
        """
        body: dict[str, Any] = {
            "source_wallets": source_wallets,
            "sizing_amount": sizing_amount,
        }
        if name is not None: body["name"] = name
        if min_trade_sol is not None: body["min_trade_sol"] = min_trade_sol
        if only_action is not None: body["only_action"] = only_action
        if sizing_mode is not None: body["sizing_mode"] = sizing_mode
        if delivery_mode is not None: body["delivery_mode"] = delivery_mode
        if webhook_url is not None: body["webhook_url"] = webhook_url
        if min_mc_usd is not None: body["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None: body["max_mc_usd"] = max_mc_usd
        return self._request("POST", "/copytrade/subscriptions", body)

    def copy_trade_get(self, subscription_id: int) -> dict[str, Any]:
        """Get one copy-trade rule by id."""
        return self._request("GET", f"/copytrade/subscriptions/{subscription_id}")

    def copy_trade_update(self, subscription_id: int, **kwargs: Any) -> dict[str, Any]:
        """Update a copy-trade rule.

        Accepts: name, source_wallets, min_trade_sol, only_action, sizing_mode,
        sizing_amount, delivery_mode, webhook_url, is_active, min_mc_usd,
        max_mc_usd. Omit a field to leave it unchanged; pass None for
        min_mc_usd / max_mc_usd to clear that bound.

        Returns ``{"subscription": {...}}``. On servers from 2026-09-25 on the
        subscription also carries ``source_wallets_tracked`` /
        ``source_wallets_untracked``, and ``warnings`` (codes
        ``untracked_source_wallets`` / ``source_wallet_tracking_unavailable``)
        appears when a wallet can never fire. When this PATCH sets a
        ``webhook_url`` on a rule that had no signing secret yet, the response
        also carries ``webhook_secret`` (shown ONCE — store it) and ``note``.
        """
        return self._request("PATCH", f"/copytrade/subscriptions/{subscription_id}", kwargs)

    def copy_trade_delete(self, subscription_id: int) -> dict[str, Any]:
        """Delete a copy-trade rule permanently."""
        return self._request("DELETE", f"/copytrade/subscriptions/{subscription_id}")

    def copy_trade_signals(
        self,
        *,
        subscription_id: int | None = None,
        since: str | None = None,
        limit: int = 50,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Recent fired copy-trade signals (up to 7 days).

        Args:
            subscription_id: Filter to one rule.
            since: ISO8601 timestamp — only signals fired at-or-after this time.
            limit: 1–500. Default 50.
            min_mc_usd: v1.6 — lower bound on MC at the source trade.
            max_mc_usd: v1.6 — upper bound on MC at the source trade.
        """
        params: dict[str, Any] = {"limit": limit}
        if subscription_id is not None:
            params["subscription_id"] = subscription_id
        if since:
            params["since"] = since
        if min_mc_usd is not None:
            params["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None:
            params["max_mc_usd"] = max_mc_usd
        return self._request("GET", "/copytrade/signals", params=params)

    # ── Coordination Alerts (PRO/ULTRA) ──

    def coordination_alerts_list(self) -> dict[str, Any]:
        """List your coordination alert rules."""
        return self._request("GET", "/kol/coordination/alerts")

    def coordination_alerts_create(
        self,
        *,
        name: str | None = None,
        min_kols: int | None = None,
        window_minutes: int | None = None,
        min_score: int | None = None,
        include_majors: bool | None = None,
        cooldown_min: int | None = None,
        score_jump_break: int | None = None,
        delivery_mode: str | None = None,
        webhook_url: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Create a coordination alert rule. Returns webhook_secret ONCE — store it.

        Args:
            name: Optional label.
            min_kols: Minimum distinct KOLs in the window (default 3).
            window_minutes: Peak-density window (1-60, default 15).
            min_score: Minimum composite score 0-100 (default 60).
            include_majors: Include WIF/BONK/POPCAT etc (default False).
            cooldown_min: Silence per (rule, token) in minutes (default 60).
            score_jump_break: Re-fire early when score jumps by N (default 10).
            delivery_mode: 'websocket', 'webhook', or 'both'.
            webhook_url: Required when delivery_mode includes 'webhook'.

        PRO=5 rules, ULTRA=20.
        """
        body: dict[str, Any] = {}
        if name is not None: body["name"] = name
        if min_kols is not None: body["min_kols"] = min_kols
        if window_minutes is not None: body["window_minutes"] = window_minutes
        if min_score is not None: body["min_score"] = min_score
        if include_majors is not None: body["include_majors"] = include_majors
        if cooldown_min is not None: body["cooldown_min"] = cooldown_min
        if score_jump_break is not None: body["score_jump_break"] = score_jump_break
        if delivery_mode is not None: body["delivery_mode"] = delivery_mode
        if webhook_url is not None: body["webhook_url"] = webhook_url
        if min_mc_usd is not None: body["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None: body["max_mc_usd"] = max_mc_usd
        return self._request("POST", "/kol/coordination/alerts", body)

    def coordination_alerts_get(self, rule_id: str) -> dict[str, Any]:
        """Get one coordination alert rule by id."""
        return self._request("GET", f"/kol/coordination/alerts/{rule_id}")

    def coordination_alerts_update(self, rule_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update a coordination alert rule.

        Accepts: name, min_kols, window_minutes, min_score, include_majors,
        cooldown_min, score_jump_break, delivery_mode, webhook_url, is_active.
        """
        return self._request("PATCH", f"/kol/coordination/alerts/{rule_id}", kwargs)

    def coordination_alerts_delete(self, rule_id: str) -> dict[str, Any]:
        """Delete a coordination alert rule permanently."""
        return self._request("DELETE", f"/kol/coordination/alerts/{rule_id}")

    # ── First-touch signal ──

    def first_touches(
        self,
        *,
        since: str | None = None,
        before: str | None = None,
        limit: int | None = None,
        kol: str | None = None,
        min_kol_winrate_7d: float | None = None,
        min_scout_tier: str | None = None,
        min_n_touches: int | None = None,
        strategy: str | None = None,
        token_age_max_min: int | None = None,
        min_first_buy_sol: float | None = None,
        mint_suffix: str | None = None,
        preset: str | None = None,
        include: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Recent first-KOL-touch events on tokens.

        Each event is the first time a tracked KOL bought a token mint. Filter
        by scout tier (S/A/B/C), KOL winrate, token age, etc. Top scouts (S-tier)
        empirically attract >=3 follow-on KOLs within 4h ~50% of the time vs
        ~14% baseline (38d backtest, n=72,549).

        Args:
            since: ISO8601 — events strictly newer than this (polling cursor).
            before: ISO8601 — events strictly older (pagination).
            limit: 1-100, default 50.
            kol: Filter to one KOL wallet (32-44 base58 chars).
            min_scout_tier: 'S' | 'A' | 'B' | 'C' (S = best). Requires n_touches >= 30.
            min_n_touches: Lower minimum sample size for scout scoring (default 30).
            preset: 'scout' or 'fresh_launch' shortcuts.
            include: 'followers_4h' to compute follower count for events >=4h old.
        """
        params: dict[str, Any] = {}
        if since is not None: params["since"] = since
        if before is not None: params["before"] = before
        if limit is not None: params["limit"] = limit
        if kol is not None: params["kol"] = kol
        if min_kol_winrate_7d is not None: params["min_kol_winrate_7d"] = min_kol_winrate_7d
        if min_scout_tier is not None: params["min_scout_tier"] = min_scout_tier
        if min_n_touches is not None: params["min_n_touches"] = min_n_touches
        if strategy is not None: params["strategy"] = strategy
        if token_age_max_min is not None: params["token_age_max_min"] = token_age_max_min
        if min_first_buy_sol is not None: params["min_first_buy_sol"] = min_first_buy_sol
        if mint_suffix is not None: params["mint_suffix"] = mint_suffix
        if preset is not None: params["preset"] = preset
        if include is not None: params["include"] = include
        if min_mc_usd is not None: params["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None: params["max_mc_usd"] = max_mc_usd
        return self._request("GET", "/kol/first-touches", params=params)

    def first_touch_subscriptions_list(self) -> dict[str, Any]:
        """List your first-touch webhook subscriptions (Ultra)."""
        return self._request("GET", "/kol/first-touches/subscriptions")

    def first_touch_subscriptions_create(
        self,
        *,
        name: str | None = None,
        filters: dict[str, Any] | None = None,
        delivery_mode: str = "webhook",
        webhook_url: str | None = None,
        min_mc_usd: float | None = None,
        max_mc_usd: float | None = None,
    ) -> dict[str, Any]:
        """Create a first-touch webhook subscription (Ultra).

        Returns webhook_secret ONCE — store it.

        Args:
            name: Optional label.
            filters: Dict with kol, mint_suffix, min_first_buy_sol, min_scout_tier, min_n_touches.
            delivery_mode: 'websocket', 'webhook', or 'both'.
            webhook_url: Required when delivery_mode includes 'webhook'.
            min_mc_usd: v1.6 — lower bound on first-touch MC.
            max_mc_usd: v1.6 — upper bound on first-touch MC.
        """
        body: dict[str, Any] = {"delivery_mode": delivery_mode}
        if name is not None: body["name"] = name
        if filters is not None: body["filters"] = filters
        if webhook_url is not None: body["webhook_url"] = webhook_url
        if min_mc_usd is not None: body["min_mc_usd"] = min_mc_usd
        if max_mc_usd is not None: body["max_mc_usd"] = max_mc_usd
        return self._request("POST", "/kol/first-touches/subscriptions", body)

    def first_touch_subscriptions_get(self, subscription_id: str) -> dict[str, Any]:
        """Get one first-touch subscription by id."""
        return self._request("GET", f"/kol/first-touches/subscriptions/{subscription_id}")

    def first_touch_subscriptions_update(self, subscription_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update a first-touch subscription. Accepts: name, filters, delivery_mode, webhook_url, is_active."""
        return self._request("PATCH", f"/kol/first-touches/subscriptions/{subscription_id}", kwargs)

    def first_touch_subscriptions_delete(self, subscription_id: str) -> dict[str, Any]:
        """Delete a first-touch subscription permanently."""
        return self._request("DELETE", f"/kol/first-touches/subscriptions/{subscription_id}")

    # ── Wallet Tracker ──

    def wallet_tracker_watchlist(self) -> dict[str, Any]:
        """List tracked wallets with labels and remaining capacity."""
        return self._request("GET", "/wallet-tracker/watchlist")

    def wallet_tracker_add(self, wallet_address: str, *, label: str | None = None) -> dict[str, Any]:
        """Add a wallet to your watchlist.

        Args:
            wallet_address: Solana wallet address to track.
            label: Optional human-readable label.
        Returns HTTP 409 if already tracked or tier limit reached.
        Limits: PRO 50, ULTRA 100, BUSINESS 500 (the Free tier has no wallet
        tracker).
        """
        body: dict[str, Any] = {"wallet_address": wallet_address}
        if label is not None:
            body["label"] = label
        return self._request("POST", "/wallet-tracker/watchlist", body)

    def wallet_tracker_remove(self, wallet_address: str) -> dict[str, Any]:
        """Remove a wallet from your watchlist."""
        return self._request("DELETE", f"/wallet-tracker/watchlist/{wallet_address}")

    def wallet_tracker_update_label(self, wallet_address: str, label: str | None) -> dict[str, Any]:
        """Update the label for a tracked wallet. Pass None to clear."""
        return self._request("PATCH", f"/wallet-tracker/watchlist/{wallet_address}", {"label": label})

    def wallet_tracker_trades(
        self,
        *,
        wallet: str | None = None,
        action: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        before: int | None = None,
        order: str | None = None,
        before_slot: int | None = None,
    ) -> dict[str, Any]:
        """Historical swap/transfer events for all watched wallets (PRO+).

        Returns ``{"events": [...], "count", "ordered_by", "next_cursor",
        "next_cursor_slot"}``. Each event carries wallet_address, label,
        event_type, action (``None`` on transfers), token_mint, token_symbol,
        token_name, sol_amount, token_amount, counterparty (only when matched),
        tx_signature, block_time (ingest clock), slot (chain order), replayed,
        ingested_at and timestamp.

        Args:
            wallet: Filter to a specific wallet address.
            action: 'buy' or 'sell'. Swaps only: transfers have action None,
                select them with event_type='transfer'. Any other value is
                rejected by the API with 400.
            event_type: Filter by event type ('swap' or 'transfer').
            limit: Max results (1–200). Default: 50.
            before: Legacy cursor for order='block_time': the previous page's
                ``next_cursor``.
            order: 'slot' (on-chain order, the default on a first page) or
                'block_time' (ingest clock, the default when ``before`` is
                passed).
            before_slot: Cursor for order='slot': the previous page's
                ``next_cursor_slot``.
        """
        params: dict[str, Any] = {"limit": limit}
        if wallet:
            params["wallet"] = wallet
        if action:
            params["action"] = action
        if event_type:
            params["event_type"] = event_type
        if before is not None:
            params["before"] = before
        if order:
            params["order"] = order
        if before_slot is not None:
            params["before_slot"] = before_slot
        return self._request("GET", "/wallet-tracker/trades", params=params)

    def wallet_tracker_summary(
        self,
        *,
        period: str = "7d",
        wallet: str | None = None,
    ) -> dict[str, Any]:
        """Per-wallet stats (swap counts, SOL bought/sold, last activity).

        Args:
            period: Time window — '24h', '7d', or '30d'. Default: '7d'.
            wallet: Filter to a specific wallet address.
        """
        params: dict[str, Any] = {"period": period}
        if wallet:
            params["wallet"] = wallet
        return self._request("GET", "/wallet-tracker/summary", params=params)

    # ── Universal wallet endpoints (PRO+, any wallet — not just curated KOLs) ──

    def wallet_stats(self, address: str) -> dict[str, Any]:
        """Aggregate stats over 90d + cross-product flags (is_kol, is_alpha_tracked
        + bot_confidence, is_deployer) for any Solana wallet. PRO+.

        v1.22 — ``flags`` also carries ``is_sniper`` / ``is_bundler`` /
        ``is_dumper`` plus a ``dump_cluster`` block (``dump_cohorts``,
        ``runner_cohorts``, ``total_cohorts``, ``as_of``; ``None`` when absent).
        ``bot_confidence`` is a string enum ``'none'`` | ``'low'`` |
        ``'medium'`` | ``'high'`` (or ``None``) — previously documented as a
        number and always ``None`` due to a server bug, now real values.
        Reputation flags are pump.fun-pipeline scoped: ``False`` = not
        observed, NOT verified clean; ``is_bundler`` is lifetime,
        ``is_dumper`` is a rolling 42-day window.

        Args:
            address: Base58 wallet address.
        """
        return self._request("GET", f"/wallet/{address}")

    def wallet_batch_classify(self, wallets: list[str]) -> dict[str, Any]:
        """v1.22 — Bulk wallet reputation flags for 1-100 wallets in one call
        (counts as 1 request). PRO+.

        Returns ``{"wallets": [...], "count": N, "as_of": ISO8601}`` — each
        entry: ``address``, ``is_sniper``, ``is_bundler``, ``is_dumper``,
        ``is_kol``, ``kol_name`` (``str | None``), ``bot_confidence``
        (``'none'`` | ``'low'`` | ``'medium'`` | ``'high'`` | ``None``), and
        ``dump_cluster`` (``{"dump_cohorts", "runner_cohorts",
        "total_cohorts", "as_of"} | None``). Flag semantics match
        :meth:`wallet_stats`: pump.fun-pipeline scoped — ``False`` means "not
        observed", NOT verified clean; ``is_bundler`` is a lifetime flag,
        ``is_dumper`` uses a rolling 42-day window (recomputed daily).

        Args:
            wallets: 1-100 base58 wallet addresses. Duplicates are removed.
        """
        return self._request("POST", "/wallet/batch/classify", {"wallets": wallets})

    def wallet_pnl(self, address: str) -> dict[str, Any]:
        """Full FIFO cost-basis PnL: realized + unrealized SOL, profit factor,
        max drawdown, hold-time stats, daily UTC PnL curve, closed positions
        sorted by pnl desc, open positions with live unrealized P&L.
        Cached with dynamic TTL — cache hits don't count against quota. PRO+.

        Args:
            address: Base58 wallet address.
        """
        return self._request("GET", f"/wallet/{address}/pnl")

    def wallet_positions(self, address: str) -> dict[str, Any]:
        """Open positions only — lighter slice of `wallet_pnl`. Shares the same
        cache. PRO+.

        Args:
            address: Base58 wallet address.
        """
        return self._request("GET", f"/wallet/{address}/positions")

    def wallet_holdings(
        self,
        address: str,
        *,
        limit: int = 200,
        min_value_usd: float = 0,
    ) -> dict[str, Any]:
        """Verified CURRENT on-chain holdings — reads the wallet's actual SPL +
        Token-2022 token accounts and SOL balance from chain, enriches with our
        price/MC/name/symbol data, and computes `transfer_delta` (on-chain amount
        minus trade-derived net position, exposing non-swap flows: airdrops,
        insider funding, wallet-hopping). Distinct from `wallet_positions`, which
        is trade-derived FIFO — holdings is "what they actually hold right now".
        ULTRA only.

        Args:
            address: Base58 wallet address.
            limit: 1-500, default 200.
            min_value_usd: Minimum USD value per holding, default 0.
        """
        params: dict[str, Any] = {"limit": limit, "min_value_usd": min_value_usd}
        return self._request("GET", f"/wallet/{address}/holdings", params=params)

    def wallet_trades(
        self,
        address: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        action: str | None = None,
        token_mint: str | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> dict[str, Any]:
        """Cursor-paginated raw trades for any wallet (default last 90 days).
        Cursor is stable across DESC pagination — pass `next_cursor` from the
        previous response to fetch older trades. PRO+.

        Args:
            address: Base58 wallet address.
            limit: 1-500, default 100.
            cursor: From `next_cursor` of a previous response.
            action: 'buy' or 'sell' filter.
            token_mint: Filter to a single token.
            since: Unix epoch seconds (default now-90d).
            until: Unix epoch seconds (default now).
        """
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if action is not None:
            params["action"] = action
        if token_mint is not None:
            params["token_mint"] = token_mint
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        return self._request("GET", f"/wallet/{address}/trades", params=params)

    # ── Price alerts (PRO/ULTRA, v1.9) ──

    def price_alerts_list(self) -> dict[str, Any]:
        """List your price alerts. PRO=5, ULTRA=25."""
        return self._request("GET", "/price-alerts")

    def price_alerts_create(
        self,
        *,
        token_mint: str,
        drop_pct: float,
        recovery_pct: float | None = None,
        name: str | None = None,
        delivery_mode: str | None = None,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a price alert. Captures baseline MC from current token_prices.
        Fires when MC drops below baseline x (1 - drop_pct/100). Optional
        recovery_pct re-fires on bounce. Returns webhook_secret ONCE -- store it.

        Args:
            token_mint: Solana mint address.
            drop_pct: Drop % threshold (0.01-99.99).
            recovery_pct: Recovery % (0.01-1000). Optional.
            name: Optional label.
            delivery_mode: 'webhook', 'websocket', or 'both'. Default 'webhook'.
            webhook_url: Required when delivery_mode includes 'webhook'.
        """
        body: dict[str, Any] = {"token_mint": token_mint, "drop_pct": drop_pct}
        if recovery_pct is not None: body["recovery_pct"] = recovery_pct
        if name is not None: body["name"] = name
        if delivery_mode is not None: body["delivery_mode"] = delivery_mode
        if webhook_url is not None: body["webhook_url"] = webhook_url
        return self._request("POST", "/price-alerts", body)

    def price_alerts_get(self, alert_id: int) -> dict[str, Any]:
        """Get one price alert by id."""
        return self._request("GET", f"/price-alerts/{alert_id}")

    def price_alerts_update(self, alert_id: int, **kwargs: Any) -> dict[str, Any]:
        """Update alert name, delivery mode, webhook URL, or is_active.
        Thresholds (drop_pct, recovery_pct) are immutable.

        Accepts: name, delivery_mode, webhook_url, is_active.
        """
        return self._request("PATCH", f"/price-alerts/{alert_id}", kwargs)

    def price_alerts_delete(self, alert_id: int) -> dict[str, Any]:
        """Delete a price alert and its event history."""
        return self._request("DELETE", f"/price-alerts/{alert_id}")

    def price_alerts_events(
        self,
        *,
        alert_id: int | None = None,
        event_type: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Fired event history (30-day retention). Filter by alert_id, event_type, since.

        Args:
            alert_id: Filter to one alert.
            event_type: 'dip' or 'recovery'.
            since: ISO 8601 — events after this timestamp.
            limit: Max events to return.
        """
        params: dict[str, Any] = {}
        if alert_id is not None: params["alert_id"] = alert_id
        if event_type is not None: params["event_type"] = event_type
        if since is not None: params["since"] = since
        if limit is not None: params["limit"] = limit
        return self._request("GET", "/price-alerts/events", params=params or None)

    # ── v1.9 new endpoints ──

    def scout_leaderboard(
        self,
        *,
        limit: int | None = None,
        scout_tier: str | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """Scout leaderboard: top KOLs ranked by scout score and swarm attraction
        rate. ULTRA only.

        Args:
            limit: Max entries.
            scout_tier: 'S', 'A', 'B', or 'C'.
            sort: 'swarm_3plus_pct', 'n_first_touches_30d', 'swarm_5plus_pct', or 'scout_score'.
        """
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        if scout_tier is not None: params["scout_tier"] = scout_tier
        if sort is not None: params["sort"] = sort
        return self._request("GET", "/kol/scouts/leaderboard", params=params or None)

    def coordination_history(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
        min_score: int | None = None,
    ) -> dict[str, Any]:
        """Coordination history: past coordination alert fires. ULTRA only.

        Args:
            limit: Max entries.
            since: ISO 8601 — events after this.
            min_score: Minimum coordination score.
        """
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        if since is not None: params["since"] = since
        if min_score is not None: params["min_score"] = min_score
        return self._request("GET", "/kol/coordination/history", params=params or None)

    def kol_consensus(self, mint: str) -> dict[str, Any]:
        """KOL consensus on a token: buyers/sellers, exit rate, net flow. ULTRA
        gets individual wallet arrays.

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/kol-consensus")

    def peak_history(self, mint: str) -> dict[str, Any]:
        """Peak MC history: ATH, decline from peak, MC at bond and at
        1h/6h/24h/7d after bond.

        Args:
            mint: Token mint address.
        """
        return self._request("GET", f"/tokens/{mint}/peak-history")
