# madeonsol-x402

[![PyPI](https://img.shields.io/pypi/v/madeonsol-x402?style=flat-square)](https://pypi.org/project/madeonsol-x402/)
[![Python](https://img.shields.io/pypi/pyversions/madeonsol-x402?style=flat-square)](https://pypi.org/project/madeonsol-x402/)
[![Downloads](https://img.shields.io/pypi/dm/madeonsol-x402?style=flat-square)](https://pypi.org/project/madeonsol-x402/)
[![GitHub stars](https://img.shields.io/github/stars/madeonsol/madeonsol-python?style=flat-square&logo=github)](https://github.com/madeonsol/madeonsol-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

> ⭐ **[Star on GitHub](https://github.com/madeonsol/madeonsol-python)** · 📂 **[Examples](./examples/)** · 📚 **[API docs](https://madeonsol.com/api-docs)**

Python SDK for the [MadeOnSol](https://madeonsol.com) Solana KOL intelligence API.

<!-- Stats below are deliberate conservative floors kept in sync with the site's canonical labels (src/lib/constants.ts KOL_COUNT_LABEL / DEPLOYERS_PROFILED_LABEL / ALPHA_WALLETS_LABEL), rounded down from a live count measured on a known date and bumped only when the real count crosses the next threshold -- never the exact live number, which changes every minute. Do not replace with a live/volatile count. -->

> Real-time Solana trading intelligence: track 2,000+ KOL wallets with <3s latency on paid keys and x402 pay-per-call (free-tier live feeds are 5-min delayed), score 85K+ Pump.fun deployers, surface deshred deploy signals ~500ms before on-chain confirmation, score 1.5M+ early-buyer wallets (incl. dump-cluster detection), push every pump.fun graduation, expose bundle-cohort supply retention (held % of supply), verify any wallet's current on-chain holdings, and stream every DEX trade. Free tier: 200 requests/day across 40+ endpoints (live feeds 5-min delayed) — no signup payment. Get a key at [madeonsol.com/pricing](https://madeonsol.com/pricing).

> **New in 1.32.0 — named subscriptions: several independent subscriptions per socket.** `subscribe(channels, filters, sub_id="...")`, `update_subscription(sub_id, filters)`, `unsubscribe("sub-id")`, `get_subscriptions()` / `await list_subscriptions()`. Each named subscription has its own channels and filters (the server caps the total per connection, default included: PRO 5, ULTRA 10, BUSINESS 20); frames carry `evt["sub_id"]`; an event matching several subscriptions is delivered once per subscription (dedupe per `(sub_id, id)`). Resume is per subscription with one commit for the connection. The plain `subscribe(channels, filters)` API is unchanged. See "Named subscriptions" in the stream section.

> **New in 1.31.0 — stream recovery: resume cursor, de-duplication, honest gaps.** The managed stream now tracks the cursor `{ instance, seq, ts }` of the last frame your handlers finished and resumes after it on every reconnect (the v1 `resume` request, with an automatic fallback to `replay_since_seq` / `replay_since_ts` on older servers). Delivery is at-least-once, de-duplicated by event `id`; new lifecycle events `cursor`, `replay`, `gap` (what could not be recovered — a `seq` gap is never loss) and `fatal`. Close codes are handled: 4001 re-fetches the token (bounded), 4002 waits ≥ 60 s instead of looping every second, 4003 stops, 4008 resumes; the backoff resets only after a `subscribed` ack. Every server `warning` frame is emitted (incl. `channels_rejected` / `channels_revoked`). `CHANNELS` gains `token:prices` (and `EVENT_NAMES` `token:price`); `client.stream(**options)` passes `resume=`, `dedupe_size=`, `max_auth_retries=`, `connection_limit_backoff=` through; the handshake token is URL-encoded. See the stream section's "Recovery" notes.

> **New in 1.29.0 — deployer reputation as-of a date, and creator-fee rewards.** `rest.deployer_as_of(wallet, date=)` binds `GET /deployer-hunter/{wallet}/as-of`: the deployer's reputation exactly as it stood on `date` (default today, UTC) — the latest write-on-change snapshot at or before it, so a backtest sees only what was knowable then. `snapshot.snapshot_date` can predate the requested date (write-on-change); `snapshot.carried` is `True` when the state was recorded earlier and had not changed by then. No snapshot at or before `date` → `as_of: False, snapshot: None` — nothing is ever synthesized. `date` must be ≥ 2026-04-07 and not in the future. `rest.deployer_rewards(wallet)` binds `GET /deployer-hunter/{wallet}/rewards`: pump.fun creator-fee rewards, answered two ways that are never merged — `collected` (what actually reached the wallet: direct vault claims kept 90 days, social-handle claims, shareholder payouts on **any** token) and `attributed` (every payout on the tokens it **deployed**, split `to_self`/`to_others` + `redirected_pct`). Every money field is `{sol, usdc, usd}`; `usd` is `None` (never a silent 0) when a SOL amount exists and no SOL price was available. `top_tokens`/`top_recipients` (≤10, USD-sorted) show where attributed fees went, recipients flagged `is_self`/`is_social_pda`. Works for non-deployers too (`is_deployer: False`, `attributed` empty). **Keyed (`msk_`) API only — not on the x402 rail; BASIC gets HTTP 403.**

> **New in 1.28.0 — token surges & revivals: momentum fires with the honest half attached.** `rest.tokens_surges(kind=, tier=, mint=, since=, before=, min_mc_usd=, max_mc_usd=, min_buys=, launchpad=, deployer_tier=, exclude_flags=, only_clean=, stats=, days=, limit=)` binds `GET /tokens/surges` (PRO+): every token momentum fire, newest first. Two kinds, one row shape. **`surge`** — a token < 30 min old whose market cap runs hard against its *launch* MC, in three tiers that each fire at most once per mint: `early` (≤10 min, ≥$12k, ≥3× launch), `strong` (≤30 min, ≥$30k, ≥6× launch **and** ≥2× the lowest sample of the last 3 min — it is climbing *now*), `breakout` (≤2 min, ≥$45k, ≥8×). A tier must be **sustained** (current tick *and* a sample ≥10 s older; nothing fires before 20 s of age) — a same-slot bundle marked to $475k at age 1 s is a spike, not a surge. **`revival`** — a token with no 1-minute trade candle for ≥24 h that starts trading again, confirmed **only by the tape** (≥5 buys, ≥$500 buy volume, MC ≥1.5× the pre-dormancy close), never by the price mark; `tier` is `None`. Hard gates on both: liquidity ≥$1.5k and ≥2 % of MC, and the MC gained must be **paid for** by buy volume (a price mark in a spoof pool moves MC on ~$0). Every row carries the burst `tape` (`source` candles / wallet_trades; `unique_buyers` only where the mint is in trade coverage — `wallet_data_available` `False` otherwise, never an inferred zero), `kol` buyers, the first-20 `early_buyers` cohort (bundled / sold / sniper wallets), `deployer` reputation and `risk_flags` (`bundled_launch`, `few_buyers`, `wash_pattern`, `thin_liquidity`, `cold_deployer`, `sniper_heavy`, `early_buyers_exiting`, `sell_pressure`, `no_tape_trades`, `no_prior_price`, `mint_authority_active`, `transfer_fee`). Rows ≥65 min old carry the +1 h `outcome`; `stats=True` prints per-(kind, tier) hit-rates (`up_1h_pct`, `median_peak_multiple`, `doubled_1h_pct`) — out-of-sample by construction. Stream: `token:surges` (events `token:surge` / `token:revival` — the same row minus `outcome`; subscribe filters `kinds`, `tiers`, `launchpads`, `exclude_flags`, `min_mc_usd` / `max_mc_usd`, `deployer_tier`) — added to `CHANNELS` / `EVENT_NAMES`; the webhook registry accepts `token:surge` / `token:revival` with the same filters. LangChain / CrewAI tool: `MadeOnSolTokenSurges`. **Keyed (`msk_`) API only — not on the x402 rail; BASIC gets HTTP 403.**

> **New in 1.27.1 — stream tokens never expire.** `POST /stream/token` (`rest.get_stream_token()`) now returns the **same token on every call, forever**. It stops working only if your subscription lapses or you call `rest.get_stream_token(rotate=True)` to replace it (the previous value keeps working for 60 s). `expires_at` and the new `next_refresh_at` are always `None` (kept for wire compatibility — do not schedule refreshes on them); the response gains `rotated` (bool) and `lifetime` (str). The server never rotates on its own and never sends `token_refresh` unless you rotated; a `4001` close means "mint again" (lapsed or rotated), never a timer. Prefer `Authorization: Bearer <token>` on the WebSocket handshake — `?token=` still works and is masked in access logs. `client.stream()` already does the right thing (it calls `get_stream_token()` on every (re)connect); no code change needed on your side.

> **New in 1.27.0 — token locks & vesting, upcoming unlocks, and pump.fun creator-fee sharing.** Five keyed (PRO+) REST bindings + two WebSocket channels. `rest.token_locks(mint, status=, program=, limit=)` — every on-chain Streamflow / Jupiter Lock / Bonfida vesting contract on a mint with the schedule (start / cliff / period / end), the terms (`cancelable_by_sender` — a cancelable lock is a weaker promise — `cancelable_by_recipient`, `transferable`, `can_topup`) and a live-derived view (`locked_raw` now, `unlocked`, `withdrawn`, `claimable`, `status`, `next_unlock`), plus a `summary` (exact `lock_count`, `distinct_lockers`, locked / deposited totals as raw + ui + usd + % of supply, `unlocking_7d_*` / `unlocking_30d_*`, nearest `next_unlock`, `active_cancelable_by_sender`). `rest.token_locks_feed(since=, before=, mint=, sender=, recipient=, program=, kind=, status=, min_usd=, min_pct_of_supply=, include_estimated=, limit=)` — cross-token feed of NEW contracts, newest first, cursor `pagination.next_since` / `next_before`. `rest.token_unlocks(within=, mint=, program=, kind=, min_usd=, min_pct_of_supply=, sort=, limit=)` — upcoming unlock EVENTS (`cliff` / `period` / `final` / `tranche`) inside `1h`…`90d` with `amount_*` and `window_amount_*`. **LP locks are NOT included** in any of the three. `rest.token_fee_shares(mint)` — the pump.fun `SharingConfig`: who receives what share (bps) of a coin's creator fees, `is_admin` / `is_social_pda` (fees earmarked for an X account etc. — `social.platform` 2 = X, `user_id` = the platform-native numeric id), `redirected_bps`, `social_bps`, `is_default: true` = 100% to the creator, plus the distributions rollup and config history. `rest.token_fee_claims(type=, mint=, recipient=, actor=, social_platform=, social_user_id=, min_sol=, since=, before=, limit=)` — the fee-event feed (`distribution` with `payouts[]`, `social_claim`, `shares_created` / `shares_updated` / `shares_reset`, `creator_transferred`, `creator_claim` only when asked via `type=`). **Fee history starts 2026-08-17.** All base-unit amounts (`*_raw`) are **strings**; ui / usd / pct are `None` when decimals or price are unknown. Streams: `token:locks` (event `token:lock`, one frame per new contract) and `token:fee_claims` (event `token:fee_claim`) — added to `CHANNELS` / `EVENT_NAMES`. LangChain / CrewAI tools: `MadeOnSolTokenLocks`, `MadeOnSolTokenLocksFeed`, `MadeOnSolTokenUnlocks`, `MadeOnSolTokenFeeShares`, `MadeOnSolTokenFeeClaims`. **Keyed (`msk_`) API only — none of these are on the x402 rail; BASIC gets HTTP 403.**

> **New in 1.26.0 — live holder census: exact holder count, labelled holders, and pools that are named, not just excluded.** `rest.token_holders(mint)` (plus `MadeOnSolTokenHolders` LangChain / CrewAI tools) binds `GET /tokens/{mint}/holders` (PRO+): every token account of the mint read from the ledger at `confirmed` and merged per owner, so `concentration.holder_count` is EXACT (distinct non-zero owners minus pools / bonding curves / burns) — never a trade-derived estimate; it is `null` only when the provider refuses the census for a mega-cap, in which case you get the top-20 view and `source.census_fallback_reason` says so. Each disclosed owner carries our labels (`deployer` / `kol` / `early_buyer` / `bundle` / `bot` / `dump_cluster` — empty means unknown to us, not clean), and `excluded[]` NAMES what was taken out of the circulating denominator: `reason` = `pool` (with `dex` + `pool_address`), `bonding_curve` (pump.fun / LaunchLab), `burn`, or `program_account` only when we genuinely cannot attribute the PDA; `pool_pct` / `burned_pct` / `program_pct` split the exclusion. Amounts are raw u64 **strings**. Disclosure: PRO ranks 1–10, ULTRA 1–50, BUSINESS 1–100 — the maths is tier-independent. Big tokens take 5–30 s upstream: you get `503 holder_scan_in_progress` with `retry_after_seconds: 20` while the scan finishes into the cache, and the retry is instant. **Keyed (v1) only — the census is not on the x402 rail.**

> **New in 1.25.0 — two prices on the trade tape, and the right one is now the default.** The trade tape now tells you what a trade actually cost. `price_sol`/`price_usd` on each trade are THIS trade's executed price — `sol_amount / token_amount`, reconciling exactly with the amounts on the same row and with the PnL endpoints. Because `sol_amount` is the wallet's net SOL movement, that is the trader's all-in effective rate: swap fee and any account rent included, not the pool mid. The market-cap tracker's canonical pool price moved to the new **`market_price_sol`/`market_price_usd`** fields — it is sampled once per token per pool update, so every trade in the same slot shares it. Until now `price_sol` carried that canonical value and disagreed with the row's own amounts by a **7.9% median** (p90 ~74%): a stale market price reads low in a pump and high in a dump, so anything you averaged out of the tape inherited the bias instead of cancelling it. Use `price_sol` for cost basis, fills and PnL; `market_price_sol` for a per-token series independent of trade size and direction. Both `rest.token_trades(mint)` and `rest.wallet_trades(address)` carry all four fields — `wallet_trades` returned amounts and no price at all before.

> **New in 1.24.0 — the Deployer Hunter surface completed.** Seven new operations that existed on the API but had no SDK binding: `deployer_leaderboard()`, `deployer_stats()`, `deployer_profile()`, `deployer_tokens()`, `deployer_alert_stats()`, `deployer_best_tokens()` and `deployer_recent_bonds()` (poll it incrementally with `next_since`). Read `bonding_rate` (lifetime) against `recent_bond_rate` (rolling) — the gap between them is the signal, not either number alone. `runner_rate` only means something once `labeled_tokens >= 3`, and an **untracked wallet returns a profile with zeroed counters, not a 404**, so check `total_deployed` before reading a 0% bond rate as a track record. Dependency ranges are now bounded to the versions actually tested (`@x402/*` `^2.x`, `@solana/kit` `^5.5.1`) instead of open-ended `>=0.0.1`, and the lazily-imported x402 peers are marked optional — a keyed install no longer pulls the whole Solana stack.

> **New in 1.23.0** — **Pool depth / price-impact + dev self-activity on the risk score.** `rest.token_depth(mint, sizes=None)` (`GET /tokens/{mint}/depth`, PRO+) answers "how much SOL does it take to move the price N%" per pool: each depth-computable pool returns `spot_price_sol`, `fee_pct`, `source` (`'stream'` for constant-product AMMs served zero-RPC from stream reserves, `'live_rpc'` for pump.fun/bonk curves priced from a live read of the curve's VIRTUAL reserves), `reserves_age_ms`, per-size `quotes` (`size_sol`, `tokens_out`, `avg_price_sol`, `price_impact_pct`), and `to_move_price` (SOL to move price `'1pct'`/`'5pct'`/`'10pct'`). `sizes` is a CSV string or list of floats (max 8, each >0 and ≤10000; default `0.5,1,5,10`); the response carries `sol_usd`, `sizes_sol`, `primary_pool`, and honesty-first `unsupported_pools` — concentrated pools (CLMM/Orca/DLMM), Meteora-DBC curves, and unclassified pools come back with a `reason` instead of a wrong number. Exposed as the `madeonsol_token_depth` (LangChain) / "MadeOnSol Token Depth" (CrewAI) tool. Plus `rest.token_risk(mint)` responses gain a top-level `dev` object — deployer self-activity for the mint: `wallet`, `launchpad`, `deployed_at`, create-tx `buy_sol`/`buy_tokens`/`buy_supply_pct`, post-create `bought_tokens_after`/`sold_tokens`/`sold_sol` with `first_sell_at`/`last_sell_at`, live on-chain `holdings_tokens`/`holdings_supply_pct`, `wallet_empty` (`bool | None`), and `transferred_out` (`bool | None` — chain balance well below the trade-derived expectation, i.e. tokens moved without a swap) — plus `as_of`. `dev` is `None` when the mint has no tracked deploy row.
>
> **New in 1.22.0** — **Batch wallet classification, token trade tape + 7 endpoints go keyless.** `rest.wallet_batch_classify(["addr1", ...])` returns reputation flags for 1–100 wallets in one call (counts as 1 request): per wallet `is_sniper` / `is_bundler` / `is_dumper` / `is_kol` (+ `kol_name`), `bot_confidence` (string enum `'none'`/`'low'`/`'medium'`/`'high'`, `None` when not alpha-tracked), and a `dump_cluster` block (`dump_cohorts`, `runner_cohorts`, `total_cohorts`, `as_of`). Flags are pump.fun-pipeline scoped — `False` = not observed, NOT verified clean; `is_bundler` is lifetime, `is_dumper` is a rolling 42d window. `rest.token_trades(mint, limit=100, cursor=None, action=None, wallet=None, since=None, until=None)` is the mint-scoped trade tape — cursor-paginated raw trades (default FULL history; capture starts 2026-04-12) with a `coverage` honesty block. Both PRO+. `wallet_stats()` flags gain the same reputation flags + `dump_cluster`, and `bot_confidence` is now correctly a string enum (a server bug made it always `None` before — real values now). `token_risk()` inputs and `sniper_recent()` deploys gain the slot-window `sniper_footprint`/`footprint` rollup. The **keyless x402 catalog grows 18 → 25**: new `MadeOnSolClient` (keyless-capable) methods `token_candles` ($0.01), `almost_bonded` ($0.01), `token_top_traders` ($0.02), `token_cap_table` ($0.02), `sniper_recent` ($0.01), `deployer_trajectory` ($0.01) — joining `token_flow` ($0.01).
>
> **New in 1.21.0** — **Verified wallet holdings.** `rest.wallet_holdings(address, limit=200, min_value_usd=0)` reads the wallet's actual SPL + Token-2022 token accounts and SOL balance directly from chain, enriches each with our price/MC/name/symbol data, and computes `transfer_delta` (on-chain amount minus trade-derived net position) to expose non-swap flows — airdrops, insider funding, wallet-hopping. Distinct from `wallet_positions` (trade-derived FIFO): holdings is "what they actually hold right now". Returns `address`, `sol_balance`, `holdings` (each with `mint`, `symbol`, `name`, `amount`, `amount_raw`, `decimals`, `token_program` (`'spl'` | `'token2022'`), `price_usd`, `value_usd`, `market_cap_usd`, `is_bonded`, `trade_derived_amount`, `transfer_delta`), a `summary` (`token_accounts`, `non_zero`, `returned`, `priced`, `total_value_usd`, `truncated`), `verified_at`, `trade_window_days`, `cache_hit`, and `ttl_seconds`. `limit` 1–500 (default 200), `min_value_usd` ≥ 0 (default 0). ULTRA only.

> **New in 1.20.0** — **Bundle-cohort holdings.** `rest.token_bundle(mint)` reveals how much of a token's supply its launch bundle still holds. The `bundle` summary carries `wallet_count`, `bundle_kind` (`'atomic_tx'` | `'same_slot'` | `'none'`), `held_pct_of_supply` (net-held / circulating supply — the HEADLINE signal, `null` when supply is unknown), `held_ratio` (net-held / buy-volume — churn-sensitive, secondary), `fully_exited`, `buy_volume` (cumulative buy volume — NOT distinct tokens, can exceed supply), and `tokens_held` (swap-derived net position). All tiers reach the endpoint, field-gated by tier: BASIC get the `bundle` summary only (`wallets: []`), PRO adds the top-10 `wallets` with flags only (`rank`, `wallet`, `held_ratio`, `has_sold`, `atomic`, `is_kol`), and ULTRA adds per-wallet identity (`kol_name`, `win_rate`, `bot_confidence`, `tokens_held`).
>
> **New in 1.19.0** — **Batch risk scoring + stream-session control.** `rest.tokens_batch_risk(["mint1", "mint2", ...])` scores 1–50 base58 mints for rug-risk/safety in a single call (counts as 1 request against quota). Returns `{ "tokens": [...], "count": N }` where each entry mirrors the single-mint `rest.token_risk()` shape (`risk_score`, `band`, `factors`, `inputs`) plus an `as_of` ISO-8601 timestamp; untracked mints come back as `{ "mint", "error": "not_tracked" }` and don't fail the batch. `tokens` preserves de-duplicated input order. PRO/ULTRA only. Plus WebSocket session control: `rest.stream_sessions()` lists your live sessions across both stream services (each with `id`, `service`, `tier`, `channels`, `connected_at`, `remote_ip`, `messages_sent`) and `rest.kill_stream_session(id)` force-terminates one and frees its connection slot — the self-serve fix for a 4002 connection-limit lockout after a deploy overlap leaves a ghost socket. Both PRO/ULTRA only, exposed as the `madeonsol_stream_sessions` / `madeonsol_kill_stream_session` (LangChain) and "MadeOnSol Stream Sessions" / "MadeOnSol Kill Stream Session" (CrewAI) tools.
>
> **New in 1.18.0** — **Almost-bonded discovery + trending sorts.** `rest.almost_bonded(min_progress=90, min_velocity_pct_per_min=0.5, deployer_tier="elite", sort="eta_asc", limit=25)` returns pre-bond pump.fun tokens near graduation, ranked by velocity (Δprogress/min) — "95% and accelerating" beats "92% stalled". Each token carries `progress_pct`, `velocity_pct_per_min`, `eta_minutes`, `stalled`, `real_sol_reserves`, `market_cap_usd`, `liquidity_usd`, `authorities_revoked`, `deployer_tier`, and `age_minutes`. `sort` is `'velocity_desc'` (default) / `'progress_desc'` / `'eta_asc'`. PRO/ULTRA only (keyed). Exposed as the `madeonsol_almost_bonded` (LangChain) / "MadeOnSol Almost Bonded" (CrewAI) tool. Plus `rest.tokens_list(sort=...)` gains four momentum sorts — `'mc_change_5m_desc'`, `'mc_change_1h_desc'`, `'volume_1h_desc'`, and `'trending'` (composite recent-volume × positive-momentum rank).
>
> **New in 1.17.0** — **Token money-flow.** `client.token_flow(mint, window="1h")` (and the async `await client.token_flow_async(mint, window="1h")`) aggregates buy/sell pressure for a token over a rolling `'1h'` or `'24h'` window. Returns `mint`, `window`, `from`, `unique_wallets`, `unique_buyers`, `unique_sellers`, `buy_count`, `sell_count`, `total_trades`, `buy_sol`, `sell_sol`, `net_sol`, and `trades_per_wallet`. PRO+ (keyed). Also: `deployer_alerts()` items now carry `deployer_sol_balance` (float | None) — the deployer wallet's SOL balance at alert time (`None` for historical rows).
>
> **New in 1.16.0** — **Live token snapshot + Signal Scorecard (keyless x402).** `client.token(mint)` returns a live `{ "token": {...} }` snapshot (`price_usd`/`price_sol`, `market_cap`, `fdv_usd`, `liquidity_usd`, `liquidity_to_mc_ratio`, `primary_dex`, `is_token_2022`, `transfer_fee_bps`, `top_buyers=[{name, sol_amount}]`). `client.signal_performance(name, history=False)` returns out-of-sample reliability for a named signal (`hit_rate`, `base_rate`, `lift`, `sample_n`, `window_days`, `test_from`/`test_to`, plus `metric_type`, `outcome`, `methodology`, `as_of`; per-day series when `history=True`) — valid names: `dump_cluster_count`, `runner_rate`, `recycled_early_buyer_count`, `coordination_count`. `client.signals()` (free) lists the signal catalog.
>
> **New in 1.15.0** — **Token OHLCV candles.** `rest.token_candles(mint, tf="1h", limit=200, from_=None, to=None)` returns 1-minute-derived OHLCV candles aggregated to a timeframe (`'1m'` | `'5m'` | `'15m'` | `'1h'` | `'4h'` | `'1d'`). Each candle has `t`, `open`, `high`, `low`, `close`, `volume_usd`, `trades`, and `market_cap_usd`. PRO returns OHLCV over the last 30 days; ULTRA adds per-candle net-flow fields (`buy_volume_usd`, `sell_volume_usd`, `net_volume_usd`, `buy_count`, `sell_count`, `volume_mev_usd`, `open_liquidity_usd`, `close_liquidity_usd`, `high_mc_usd`, `low_mc_usd`) and full history.
>
> **New in 1.14.0** — **Token risk score.** `rest.token_risk(mint)` returns a transparent 0–100 rug-risk/safety score (higher = riskier) with a `band` (`'safe'` | `'caution'` | `'danger'`), an explainable `factors` array, and the raw `inputs` (mint/freeze authority, liquidity, liq-to-MC ratio, transfer fee, launch cohort, deployer bond rate, KOL signal, blacklist). PRO/ULTRA only.
>
> **New in 1.13.0** — `rest.tokens_list()` gains three new filter params: `min_liq_mc_ratio`, `max_liq_mc_ratio`, and `deployer_tier` (`'elite'` | `'good'` | `'moderate'` | `'rising'` | `'cold'` | `'unranked'`). Response items now include `liquidity_to_mc_ratio` and `deployer_tier`. KOL leaderboard entries now include `median_hold_minutes_30d` and `percentile_early_entry_30d`. `/token/{mint}` and `/token/batch` responses now include `liquidity_to_mc_ratio`, `launch_cohort_sol`, and `launch_cohort_size`.
>
> **New in 1.12.1** — Deployer alerts/profiles now carry `runner_rate` + `labeled_tokens` (fraction of a deployer's labeled tokens that ran vs dumped, gate on `labeled_tokens` >= 3) plus `avg_time_to_bond_minutes`.

> **New in 1.12** — **Graduation events + dump-cluster detection.** Subscribe `token:graduations` for every pump.fun bond in real time (tracked deployer or not). Buyer-quality `breakdown` adds `dump_cluster_count` (out-of-sample: 3+ → 94% dump vs 61% base) + `recycled_early_buyer_count`. DEX firehose: replay buffer deepened to ~5 min; mint-scoped subs get in-band `dex:graduations` frames.

> **New in 1.10** — **Deshred Sniper.** `client.rest.sniper_recent()` — deshred deploy feed ~500ms before on-chain confirmation. PRO: elite/good. ULTRA: all tiers + `sniper_watchlist_add()`. Use `sniper:deploys` WebSocket for push.
>
> **New in 1.9** — **Price alerts, scout leaderboard, coordination history.** `client.rest.price_alerts_create()` (PRO=5, ULTRA=25). `scout_leaderboard()`, `kol_consensus()`, `peak_history()`, `coordination_history()`. `wallet_stats()` now returns `derived`: win_rate, roi, verdict, biggest_miss.
>
> **New in 1.8** — **Universal Wallet API.** `client.rest.wallet_stats()`, `wallet_pnl()`, `wallet_positions()`, `wallet_trades()` — FIFO cost-basis PnL for any Solana wallet. PRO+. Cache hits free.
>
> **New in 1.7.1** *(2026-05-13)* — Velocity field shape corrected to match the API: `mc_change_pct`, `volume_usd`, `mev_volume_pct` are top-level on the token response, each keyed by `'5m'`/`'15m'`/`'1h'`/`'2h'`/`'4h'`. The 1.7.0 README documented a `velocity[window]` shape that didn't match the wire format.
>
> **New in 1.7.0** *(2026-05-12)* — **Token directory + account inspection.** `client.rest.tokens_list(min_liq=10000, min_volume_1h_usd=5000, max_mev_share_pct=60, mc_change_1h_min_pct=20, sort="mc_desc", min_liq_mc_ratio=0.05, deployer_tier="elite")` filters every active mint by MC band, liquidity floor, primary DEX, authority/safety flags, computed 1h volume, MEV-share ceiling, MC-change deltas, liq/MC ratio, and deployer tier. Response items include `liquidity_to_mc_ratio` and `deployer_tier`. Default `min_liq=2000` skips phantom-MC dust; pass `min_liq=0` to opt out. `client.rest.me()` — read your tier, daily/burst quota state, and per-feature usage in one call (no header parsing). Velocity / MEV-share fields added to every token response: `mc_change_pct`, `volume_usd`, `mev_volume_pct` (each keyed by `'5m'`/`'15m'`/`'1h'`/`'2h'`/`'4h'`) plus `history_age_seconds`. `/token/{mint}` 400s now ship structured `code`, `reason`, `received_length`, `example`, and `docs`. Deprecated `avg_entry_mc_usd` fully removed.

## Quick start (10 seconds)

```bash
pip install madeonsol-x402
```

```python
from madeonsol_x402 import MadeOnSolClient
client = MadeOnSolClient(api_key="msk_...")  # free tier at https://madeonsol.com/pricing
trades = client.kol_feed(limit=5, action="buy")
```

## Authentication

Two options:

| Method | Parameter / Env var | Best for |
|---|---|---|
| **MadeOnSol API key** (recommended) | `api_key` / `MADEONSOL_API_KEY` | Developers — [get a free key](https://madeonsol.com/pricing) |
| x402 micropayments | `private_key` / `SVM_PRIVATE_KEY` | AI agents with Solana wallets |

> **v1.0 breaking change:** RapidAPI auth has been removed. The MadeOnSol RapidAPI marketplace was retired on 2026-04-19. If you were using `rapidapi_key=` or `RAPIDAPI_KEY`, get a free `msk_` key at [madeonsol.com/pricing](https://madeonsol.com/pricing).

## Install

```bash
pip install madeonsol-x402                    # core SDK
pip install madeonsol-x402[langchain]         # + LangChain tools
pip install madeonsol-x402[crewai]            # + CrewAI tools
```

> x402 dependencies are only needed when using `private_key` / `SVM_PRIVATE_KEY`.

## Quick Start

```python
from madeonsol_x402 import MadeOnSolClient

client = MadeOnSolClient(api_key="msk_your_api_key_here")

# Real-time KOL trades — each trade now includes
# market_cap_usd_at_trade and price_usd_at_trade (real-time MC at the
# moment the swap fired, sourced from our in-memory price tracker).
trades = client.kol_feed(limit=10, action="buy")
for t in trades["trades"]:
    print(f'{t["kol_name"]} bought {t["token_symbol"]} for {t["sol_amount"]:.2f} SOL @ MC ${t.get("market_cap_usd_at_trade") or "?"}')

# KOL convergence signals
signals = client.kol_coordination(period="24h", min_kols=3)

# KOL leaderboard — 180 days of history
leaders = client.kol_leaderboard(period="7d")  # today | 7d | 30d | 90d | 180d

# Deployer alerts (all tiers can filter by tier)
# Each alert carries deployer_sol_balance (float | None) — deployer wallet
# SOL balance at alert time (None for historical rows).
alerts = client.deployer_alerts(limit=10)
elite_only = client.deployer_alerts(limit=10, tier="elite")

# Token money-flow over a rolling window (PRO+) — sync
flow = client.token_flow("So11111111111111111111111111111111111111112", window="1h")
print(flow["net_sol"], flow["unique_buyers"], flow["unique_sellers"])

# Alpha wallet leaderboard (REST)
top = client.rest.alpha_leaderboard(period="30d", sort="win_rate")

# Wallet Tracker (REST)
client.rest.wallet_tracker_add("WALLET_ADDRESS", label="whale")
events = client.rest.wallet_tracker_trades(limit=50)

# Inspect rate-limit headers from the most recent REST call
print(client.rest.last_rate_limit)
# {'limit': 100, 'remaining': 92, 'reset': 1714000000, 'request_id': 'rid_abc123'}
```

### Token money-flow *(new in 1.17)*

`token_flow(mint, window="1h")` aggregates buy/sell pressure for a token over a rolling `'1h'` or `'24h'` window. PRO+ (keyed). Both sync and async variants are available:

```python
import asyncio
from madeonsol_x402 import MadeOnSolClient

client = MadeOnSolClient(api_key="msk_...")
mint = "So11111111111111111111111111111111111111112"

# Sync
flow = client.token_flow(mint, window="1h")
print(flow["net_sol"], flow["buy_sol"], flow["sell_sol"])

# Async
async def main():
    flow = await client.token_flow_async(mint, window="24h")
    print(flow["unique_wallets"], flow["trades_per_wallet"])

asyncio.run(main())
```

Response keys: `mint`, `window`, `from`, `unique_wallets`, `unique_buyers`, `unique_sellers`, `buy_count`, `sell_count`, `total_trades`, `buy_sol`, `sell_sol`, `net_sol`, `trades_per_wallet`.

## Real-time streaming *(new in 1.11)*

Managed WebSocket stream — auto-reconnect, token fetch (the token never expires; `get_stream_token()` is called on every (re)connect), and typed callbacks handled for you. Needs the `stream` extra: `pip install "madeonsol-x402[stream]"`.

```python
import asyncio
from madeonsol_x402 import MadeOnSolREST

client = MadeOnSolREST(api_key="msk_...")

async def main():
    stream = client.stream()

    @stream.on("kol:trade")
    async def on_trade(data, evt):
        print(data["token_symbol"], data["action"])

    stream.subscribe(["kol:trades", "deployer:alerts"])
    await stream.run()   # blocks; manages connection + reconnects

asyncio.run(main())
```

Channels: `kol:trades`, `kol:coordination`, `kol:first_touches`, `deployer:alerts`, `wallet_tracker:events`, `copytrade:signals`, `price_alert:events`, `sniper:deploys`, `token:graduations` (every pump.fun graduation in real time, tracked deployer or not), `token:prices` (event `token:price` — per-mint price/MC ticks; PRO+, REQUIRES `filters={"mints": [...]}` — PRO 25 / ULTRA 100 / BUSINESS 250 per connection; a state stream, never replayed), `token:locks` (event `token:lock` — every NEW Streamflow / Jupiter Lock / Bonfida lock or vesting contract, PRO+; LP locks not included), `token:fee_claims` (event `token:fee_claim` — every pump.fun fee event: distributions, social-handle claims, SharingConfig changes, PRO+; history starts 2026-08-17), `token:surges` (events `token:surge` — a token < 30 min old running ≥3× / ≥6× / ≥8× its launch MC, `tier` early / strong / breakout, each once per mint, sustained — and `token:revival` — ≥24 h with no trade candle, then confirmed buys on the tape, `tier` `None`; the same row as `rest.tokens_surges()` minus `outcome`, `risk_flags` included; subscribe filters `kinds`, `tiers`, `launchpads`, `exclude_flags`, `min_mc_usd` / `max_mc_usd`, `deployer_tier`; PRO+). Lifecycle events: `open`, `close`, `reconnect`, `subscribed`, `heartbeat`, `warning`, `cursor`, `replay`, `gap`, `fatal`, `error`.

### Recovery: cursor, resume, de-duplication *(new in 1.31.0)*

The stream keeps a **resume cursor** `{"instance", "seq", "ts"}` — the position of the last frame your handlers finished — and on every reconnect asks the server to resume after it (`subscribe {…, "resume": …}`).

- **"Processed"** means the handler returned (sync) or was awaited to completion (async). Handlers run one frame at a time, so the cursor never passes a frame still being handled. A handler that raises still counts as processed; the exception goes to `error`.
- **At-least-once, never exactly-once.** After a reconnect a frame can arrive again. The client drops ids it delivered recently (the last 10,000, `dedupe_size=`); anything you persist should still dedupe on `evt["id"]`. Replayed frames carry `evt["replayed"] is True`.
- **Persistence.** The cursor lives in memory. Save `stream.get_cursor()` (or on every `cursor` event) and pass it back as `client.stream(resume=saved)` to continue after a process restart. Persist the committed cursor, never `get_progress()`.
- **Committed cursor vs progress.** `get_cursor()` is the COMMITTED, safe cursor — persist and resume from this one. `get_progress()` is what has been received and handled (replayed frames included) and is not safe to resume from. Live frames commit as they are handled. Replayed frames never commit: the server replays channel by channel, so only a `replay_end` the server calls complete — or one whose gaps are all final — commits, at the server's `last_seq` / `last_ts`. If a recovery is incomplete, or the socket closes mid-replay, the committed cursor stays at the pre-resume point, and live frames after it are delivered but not committed until a later recovery completes (`is_recovery_incomplete()`). **Trade-off:** the next reconnect re-requests the unrecovered range from the old cursor, and what arrives twice is dropped by id. Call `accept_gap()` once you have backfilled the range the `gap` event named, or decided to skip it. A gap the server calls final is handled by `on_unrecoverable_gap` (below).
- **Gaps: what is known, and who decides.** A `gap` event says which channels the server could not rebuild, the **range that may be incomplete** (`skipped["from"]` → `skipped["to"]`, plus `from`), the server's `reason`, whether it is `permanent`, and the bounds the server reported (`limits`, and per-channel `time_basis` / `truncated_at_ts` / `retry_after_ms` under `channels`). Events in that range **may** be missing — the number cannot be known, so it is never stated. Backfill the range from REST if you need certainty.
  - **Transient** (`retryable: True` — `backpressure`, `closed`, `source_busy`, `source_error`, `late_ingest_possible`, `row_cap`): the committed cursor stays put, live frames do not commit, and the client resumes again after the server's `retry_after_ms` (for `row_cap`, from `resume_ts_hint`), then on every reconnect. `resume_ts_hint` is used only when every incomplete **retryable** channel is `row_cap` (a channel whose gap is final does not block it, and is still reported); otherwise the retry asks from the committed cursor again. The client asks again after the server’s `retry_after_ms` at most `max_resume_retries` times per connection (default 5; the budget resets on every reconnect); when that budget is spent the gap event says `exhausted: True`, the cursor stays where it is, and the next reconnect resumes again.
  - **Final** (`retryable: False` — `not_reconstructable`, `window_exceeded`, and an older server's `ring_truncated` / `instance_changed`): asking again can never fill it. **The SDK then decides to continue** — that is the client's decision, not your approval — and reports it on the same `gap` event with `advanced_past_gap: True`, `source: "auto"` and the range being skipped, *before* the cursor moves. Pass `on_unrecoverable_gap="stop"` to keep the cursor instead: the stream stops and emits `fatal` with the gap, and you decide (`accept_gap()` then `run()` again continues; `accept_gap()` reports the same gap with `source: "manual"`).
- **Older servers.** Against a server that does not understand `resume` yet, the client falls back to `replay_since_seq` (same server process) or `replay_since_ts` (the server restarted). That only covers the server's in-memory buffer (minutes), and a restart is reported as a `gap` with `instance_changed`.
- **Close codes.** `4001` → the token is re-fetched and the client reconnects (`max_auth_retries=`, default 3, then `fatal` and `run()` returns); `4002` connection limit → `error` (`StreamConnectionLimitError`) plus a wait of at least 60 s (`connection_limit_backoff=`); `4003` → `fatal`, `run()` returns; `4008` slow consumer → reconnect and resume. The backoff resets only when the server acks a subscribe. `stream.last_close` keeps the last `(code, reason)`, and the `close` event carries `{"code", "reason"}`.
- **Warnings.** `warning` fires for every server warning frame, including `channels_rejected` and `channels_revoked` (revoked channels are removed from the subscription so reconnects do not re-request them); with no handler registered they go through `warnings.warn`.

```python
stream = client.stream(resume=load_cursor())   # None on first run

@stream.on("*")
async def persist(data, evt):
    await store.upsert(evt["id"], data)        # the cursor advances after this returns

stream.on("cursor", save_cursor)               # {"instance", "seq", "ts"}
stream.on("gap", lambda g: print("may be missing:", g["reasons"], g["skipped"]))  # g["advanced_past_gap"]
stream.on("fatal", lambda f: print("stream stopped:", f["code"], f["reason"]))
```

### Named subscriptions *(new in 1.32.0)*

One socket can hold several independent subscriptions, each with its own channels and filters; the server caps the total per connection, the default one included (PRO 5, ULTRA 10, BUSINESS 20). `subscribe(channels, filters)` stays the connection's `"default"` subscription and its wire is unchanged; `subscribe(channels, filters, sub_id="...")` opens a named one (1-64 characters of `A-Z a-z 0-9 _ . -`). A frame delivered under a named subscription carries `evt["sub_id"]`. **An event that matches several subscriptions is delivered once per matching subscription**, each copy stamped with its `sub_id`: the client dedupes per `(sub_id, id)`, so the same event can legitimately reach a handler twice, under two sub_ids. Filters of one subscription never affect another. `update_subscription(sub_id, filters)` REPLACES that subscription's filters (`"default"` addresses the plain one), `unsubscribe("my-sub")` / `unsubscribe(sub_id="my-sub")` removes it, `get_subscriptions()` is the local view and `await stream.list_subscriptions()` asks the server (`list` / `subscriptions`). Server refusals arrive as `warning` frames carrying the `sub_id` and one of `invalid_sub_id`, `too_many_subscriptions`, `unknown_sub_id`, `invalid_filters`, `channels_rejected`, `channels_revoked`, `replay_in_progress`; a subscription refused as `too_many_subscriptions` or `invalid_sub_id` is dropped locally so reconnects stop re-requesting it. Lifecycle events `updated` and `unsubscribed` surface the server acks.

**Resume with several subscriptions** is per subscription: on every reconnect each subscription is re-sent with the same cursor, the server serves one replay per subscription, one after another (`replay_start` … `replay_end` each carry the `sub_id`; live frames are held until the last one ends), and the cursor commits once ALL of them have ended, at the smallest `last_seq` / `last_ts` across them. The `replay` event lists `subscriptions` and the raw `ends` per subscription; a gap's `channels` entries are keyed `sub_id/channel` for named subscriptions, and an incomplete retryable replay is retried for those subscriptions only. Against an older server that ignores `sub_id`, the client emits `warning` `named_subscriptions_unsupported` once.

```python
stream = client.stream()
stream.subscribe(["kol:trades"], {"action": "buy", "min_sol": 1}, sub_id="kol-buys")
stream.subscribe(["deployer:alerts"], {"deployer_tier": ["elite"]}, sub_id="deploys")

@stream.on("kol:trade")
def on_event(data, evt):
    print(evt.get("sub_id"), data)   # "kol-buys"

stream.update_subscription("kol-buys", {"action": "buy", "min_sol": 5})
stream.unsubscribe("deploys")
await stream.run()
```

## LangChain

```python
from madeonsol_x402.langchain_tools import ALL_TOOLS

# Set MADEONSOL_API_KEY or SVM_PRIVATE_KEY env var
agent = create_react_agent(llm, tools=ALL_TOOLS)
```

## CrewAI

```python
from madeonsol_x402.crewai_tools import ALL_TOOLS

agent = Agent(role="Solana Analyst", tools=ALL_TOOLS)
```

## Endpoints

### KOL Intelligence (x402-priced — also reachable via `msk_` API key)

| Method | Description |
|---|---|
| `kol_feed()` | Real-time KOL trade feed (1,000+ wallets) |
| `kol_coordination()` | Multi-KOL convergence signals |
| `kol_leaderboard()` | PnL and win rate rankings — windows: today, 7d, 30d, 90d, 180d (180-day retention) |
| `kol_pairs()` | KOL affinity matrix — which KOLs co-trade the same tokens |
| `kol_hot_tokens()` | KOL momentum tokens — accelerating buy interest |
| `kol_trending_tokens()` | Tokens ranked by KOL buy volume |
| `kol_token_entry_order(mint)` | Ranked KOL first-buyer order for a token |
| `kol_compare_wallets(wallets)` | Side-by-side comparison of 2–5 KOL wallets |
| `kol_alerts_recent()` | Live KOL alert feed — clusters, fresh-token buys, heating-up |
| `deployer_alerts()` | Pump.fun deployer launches with KOL enrichment |
| `wallet_stats(address)` | **New 1.8** · Universal wallet stats (90d) + cross-product flags. $0.005 |
| `wallet_pnl(address)` | **New 1.8** · FIFO cost-basis PnL: realized + unrealized, profit factor, drawdown, daily curve, closed + open positions. $0.02 |
| `wallet_positions(address)` | **New 1.8** · Open positions with live unrealized from market-cap tracker. Shares /pnl cache. $0.01 |
| `wallet_trades(address, ...)` | **New 1.8** · Cursor-paginated raw trades with action / token / since-until filters. $0.005 |
| `token(mint)` | **New 1.16** · Live token snapshot — price_usd/price_sol, market_cap, fdv_usd, liquidity_usd, liquidity_to_mc_ratio, primary_dex, is_token_2022, transfer_fee_bps, top_buyers |
| `signal_performance(name, history=False)` | **New 1.16** · Signal Scorecard — out-of-sample hit_rate/base_rate/lift/sample_n per signal (dump_cluster_count, runner_rate, recycled_early_buyer_count, coordination_count) |
| `signals()` | **New 1.16** · Free — signal catalog with per-signal methodology and performance_endpoint |
| `token_flow(mint, window="1h")` | **New 1.17** · PRO+ · Token money-flow over a rolling 1h/24h window — unique wallets/buyers/sellers, buy/sell counts + SOL, net SOL flow, trades per wallet. Async: `token_flow_async(mint, window="1h")` |
| `token_candles(mint, tf=, limit=, from_=, to=)` | **New 1.22** · OHLCV candles, keyless (PRO slice: 30d). $0.01 |
| `almost_bonded(**filters)` | **New 1.22** · Pre-bond pump.fun tokens near graduation, ranked by velocity. $0.01 |
| `token_top_traders(mint, limit=, sort=, window_days=, min_bought_sol=)` | **New 1.22** · Wallets ranked by realized PnL/ROI on a token, enriched with KOL/alpha identity. $0.02 |
| `token_cap_table(mint)` | **New 1.22** · Early-buyer cap table with PnL/exit/bundle/KOL flags. $0.02 |
| `sniper_recent(since=, deployer_tier=, min_bond_rate=, limit=)` | **New 1.22** · Deshred pre-confirm deploy feed (keyless: elite/good scope) with per-deploy `footprint` snipe rollup. $0.01 |
| `deployer_trajectory(wallet)` | **New 1.22** · Deployer skill curve — streaks, rolling bond rate, trend. $0.01 |
| `discovery()` | Free — list all endpoints and prices (25 keyless x402 endpoints) |

### REST API — KOL/deployer detail

| Method | Description |
|---|---|
| `rest.kol_pnl(wallet, period=)` | Deep per-wallet PnL: equity curve, risk metrics, closed positions. ULTRA adds open positions (tokens bought but not yet sold). |
| `rest.kol_timing(wallet, period=)` | KOL entry/exit timing profile — available on all tiers |
| `rest.deployer_trajectory(wallet)` | Deployer skill curve — streaks, rolling bond rate, trend — available on all tiers |
| `rest.deployer_history(wallet, limit=90)` | **New 1.20** | Daily reputation time-series — backtest "was this deployer elite when it launched token X?" without look-ahead bias. `snapshots` array of per-day `tier`/`bonding_rate`/`avg_peak_mc`. `limit` 1–365 |

### Alpha Wallet Intelligence

Scored from 1.5M+ early-buyer records (wallets seen in the first 20 buyers of Pump.fun tokens).

| Method | Tier | Description |
|---|---|---|
| `rest.alpha_leaderboard(period=, min_tokens=, sort=, exclude_bots=)` | All | Up to 100 results on Free/Pro; ULTRA unlocks 500 + bot signals |
| `rest.alpha_wallet(wallet)` | ULTRA | Full per-token breakdown + bot_signals array |
| `rest.alpha_linked(wallet)` | ULTRA | Wallets behaviorally linked (co-bought 3+ tokens within 2s) |

### Token Quality

| Method | Tier | Description |
|---|---|---|
| `rest.token_cap_table(mint)` | PRO+ | First non-deployer early buyers, enriched with PnL/KOL/bot flags. PRO=10, ULTRA=20 |
| `rest.token_buyer_quality(mint)` | All | 0–100 buyer-quality score + full breakdown (5-min cached) |
| `rest.token_risk(mint)` | PRO+ | Transparent 0–100 rug-risk/safety score with `band`, explainable `factors`, and raw `inputs` |
| `rest.token_bundle(mint)` | **New 1.20** · All | Bundle-cohort holdings — `bundle` summary with `held_pct_of_supply` (headline), `bundle_kind`, `fully_exited`. BASIC=summary only, PRO=+top-10 wallet flags, ULTRA=+identity |
| `rest.tokens_batch_risk(mints)` | **New 1.19** · PRO+ | Bulk risk scoring for 1–50 mints in one call (1 request). Each entry mirrors `token_risk` + `as_of`; untracked mints → `{mint, error: "not_tracked"}` |
| `rest.token_candles(mint, tf, limit, from_, to)` | PRO+ | 1-minute-derived OHLCV candles by timeframe. PRO=OHLCV/30d, ULTRA=+net flow/full history |
| `rest.token_trades(mint, limit=, cursor=, action=, wallet=, since=, until=)` | **New 1.22** · PRO+ | Mint-scoped trade tape — cursor-paginated raw trades, default FULL history (capture starts 2026-04-12, pump.fun-pipeline scoped; see the `coverage` block) |
| `rest.token_pools(mint)` | **New 1.20** · PRO+ | Per-venue liquidity map — every DEX pool a token trades in, live vs parked. `pools` array + `summary` with `total_liquidity_usd`, `primary_dex`, `top_pool_share_pct` |
| `rest.token_holders(mint)` | **New** · PRO+ | Live holder census + concentration — who holds NOW. `concentration.holder_count` is EXACT (mint-scoped `getProgramAccounts` census; `None` only when the provider refuses a mega-cap → top-20 fallback with `source.census_fallback_reason`, never trade-estimated). Each disclosed owner labelled `deployer`/`kol`/`early_buyer`/`bundle`/`bot`/`dump_cluster`; pools / bonding curves / burns EXCLUDED from the circulating denominator and NAMED in `excluded[]` (`pool`+`dex`+`pool_address` \| `bonding_curve` \| `burn` \| `program_account`). Amounts are raw u64 STRINGS. Disclosure PRO=10, ULTRA=50, BUSINESS=100. Big tokens: first call may be HTTP 503 `holder_scan_in_progress` (`retry_after_seconds: 20`) — scan continues + cached, retry is instant. Exposed as `madeonsol_token_holders` (LangChain) / "MadeOnSol Token Holders" (CrewAI). Key-mode only (not on the x402 rail) |
| `rest.token_locks(mint, status=, program=, limit=)` | **New 1.27** · PRO+ | Token locks & vesting on a mint — every Streamflow / Jupiter Lock / Bonfida vesting contract: schedule (start / cliff / period / end), terms (`cancelable_by_sender` / `_recipient`, `transferable`, `can_topup`), live-derived `locked_raw` / `unlocked` / `withdrawn` / `claimable` / `status` / `next_unlock`, and a `summary` (exact `lock_count`, `distinct_lockers`, locked / deposited raw + ui + usd + % of supply, `unlocking_7d_*` / `unlocking_30d_*`, `active_cancelable_by_sender`). Base-unit amounts are STRINGS; ui/usd/pct `None` when unknown. **LP locks NOT included.** Key-mode only |
| `rest.token_locks_feed(since=, before=, mint=, sender=, recipient=, program=, kind=, status=, min_usd=, min_pct_of_supply=, include_estimated=, limit=)` | **New 1.27** · PRO+ | Cross-token feed of NEW lock / vesting contracts, newest first (+ per-row `token` block). Cursors `pagination.next_since` / `next_before`; pushed live on WS `token:locks`. Backfilled Jupiter rows excluded unless `include_estimated=True`. Key-mode only |
| `rest.token_unlocks(within=, mint=, program=, kind=, min_usd=, min_pct_of_supply=, sort=, limit=)` | **New 1.27** · PRO+ | Upcoming unlock EVENTS (`cliff` / `period` / `final` / `tranche`) across all active contracts inside `within=1h…90d` (default `7d`): `unlock_at`, `in_seconds`, `amount_*`, `window_amount_*` (total release over the window), `token`, `lock`. `sort=soonest|largest_usd|largest_pct`. Key-mode only |
| `rest.token_fee_shares(mint)` | **New 1.27** · PRO+ | pump.fun creator-fee `SharingConfig` on a mint: `shareholders[]` with `share_bps`, `is_admin`, `is_social_pda` (+ `social.platform` 2 = X, `social.user_id` numeric id, lifetime claimed), `redirected_bps`, `social_bps`, `is_default` (`True` = 100% to creator), `config.source` `stream`\|`chain`; `distributions` rollup (per-recipient received, `past_recipients`), `history`, `recent_distributions`. Quote base-unit amounts are STRINGS. Fee history starts 2026-08-17. Key-mode only |
| `rest.token_fee_claims(type=, mint=, recipient=, actor=, social_platform=, social_user_id=, min_sol=, since=, before=, limit=)` | **New 1.27** · PRO+ | pump.fun fee-event feed, newest first: `distribution` (+ `payouts[]`), `social_claim`, `shares_created` / `shares_updated` / `shares_reset`, `creator_transferred`; `creator_claim` only when requested via `type=`. Cursor `pagination.next_since`; pushed live on WS `token:fee_claims`. History starts 2026-08-17. Key-mode only |
| `rest.tokens_surges(kind=, tier=, mint=, since=, before=, min_mc_usd=, max_mc_usd=, min_buys=, launchpad=, deployer_tier=, exclude_flags=, only_clean=, stats=, days=, limit=)` | **New 1.28** · PRO+ | Token momentum fires, newest first — `kind='surge'` (token < 30 min old vs its LAUNCH MC; `tier` `early` ≤10 min ≥$12k ≥3× · `strong` ≤30 min ≥$30k ≥6× and ≥2× the 3-min low · `breakout` ≤2 min ≥$45k ≥8×; each once per mint, sustained ≥10 s) or `'revival'` (no trade candle ≥24 h, then ≥5 buys / ≥$500 buy volume / ≥1.5× the pre-dormancy MC on the tape — never a price mark; `tier` `None`). Each row: burst `tape` (`unique_buyers` `None` outside trade coverage), `kol`, `early_buyers` (bundled / sold / sniper), `deployer`, `risk_flags`, and `outcome` (+1 h MC / peak / low) once ≥65 min old. `stats=True` = per-(kind, tier) hit-rates over `days`. `exclude_flags` drops rows carrying ANY listed flag; `only_clean=True` = no flags. Cursors `pagination.next_since` / `next_before`; pushed live on WS `token:surges`. Retention 60 d. Exposed as `madeonsol_tokens_surges` (LangChain) / "MadeOnSol Token Surges" (CrewAI). Key-mode only |

### Deshred Sniper Alerts *(new in 1.10)*

The fastest path to a new pump.fun launch. Deploys are reconstructed from shred-level (**deshred**) data and surface **~500ms before the chain confirms them**. **PRO** sees elite + good deployers; **ULTRA** sees every tier and can keep a custom deployer watchlist. For live push use the `sniper:deploy` webhook or the `sniper:deploys` WebSocket channel.

| Method | Tier | Description |
|---|---|---|
| `rest.sniper_recent(limit=, deployer_tier=, min_bond_rate=, since=, watchlist=)` | PRO+ | Deshred deploy feed, newest first. PRO=elite/good, ULTRA=all tiers. `watchlist=True` (ULTRA) narrows to your watchlist |
| `rest.sniper_by_deployer(wallet, limit=)` | ULTRA | Deshred deploys for one deployer |
| `rest.sniper_watchlist()` | ULTRA | List your custom deployer watchlist (max 50) |
| `rest.sniper_watchlist_add(wallet=/wallets=, label=)` | ULTRA | Add one or many deployers |
| `rest.sniper_watchlist_remove(wallet)` | ULTRA | Remove a deployer |

```python
feed = client.rest.sniper_recent(limit=50, min_bond_rate=0.5)
client.rest.sniper_watchlist_add(wallets=["7dEx...4pQ8", "9aBc...2zZ1"], label="alpha devs")
tracked = client.rest.sniper_recent(watchlist=True)  # ULTRA — only your tracked deployers
```

### KOL Coordination Alerts (v1.1 — push signals)

Real-time push alerts when a cluster of KOLs co-buys the same token. Fires within ~1s of the triggering trade (pg_notify push, not polling). Delivered via WebSocket (`kol:coordination` channel, user-scoped) and/or HMAC-signed webhook. PRO=5 rules, ULTRA=20.

```python
res = client.rest.coordination_alerts_create(
    name="fresh pump cluster",
    min_kols=4,
    window_minutes=15,     # peak-density window (1-60)
    min_score=70,          # 0-100 composite score cutoff
    include_majors=False,  # filter WIF/BONK/POPCAT
    cooldown_min=60,       # one fire per (rule, token) per 60min...
    score_jump_break=10,   # ...unless score jumps +10 vs last fire
    delivery_mode="both",
    webhook_url="https://you.com/hooks/coord",
)
# store res["webhook_secret"] — shown ONCE
```

`coordination_alerts_list()`, `coordination_alerts_get(id)`, `coordination_alerts_update(id, **fields)`, `coordination_alerts_delete(id)`.

**Webhook signature:** `X-MadeOnSol-Signature: sha256=<hmac>` where `hmac = HMAC-SHA256(webhook_secret, timestamp + "." + rawBody)`, and `X-MadeOnSol-Timestamp` carries the unix seconds used.

**The `kol_coordination()` response** now includes v1.1 fields: `peak_window_start/end`, `peak_kols`, `peak_buys` (the busiest slice within the period), `exited_count` + per-KOL `exited` (net-flow-negative wallets), and `coordination_score` (0-100). Pass `min_score=`, `window_minutes=`, `include_majors=` to filter.

### KOL First-Touch Signal *(new in 1.3)*

Every "first KOL buy on a token mint" event — when a tracked KOL is the first of the cohort to touch a token. Filterable by **scout tier** (S/A/B/C from `mv_kol_scout_score`), KOL winrate, token age, mint suffix.

**Backtest:** S-tier scouts attract ≥3 follow-on KOLs within 4h ~50% of the time vs ~14% baseline (38d / 491k buys / 72,549 events). Public leaderboard at [madeonsol.com/kol/scouts](https://madeonsol.com/kol/scouts).

```python
# REST query — S-tier scouts on tokens younger than 1h
events = client.rest.first_touches(preset="scout", min_scout_tier="S", limit=20)
for e in events["events"]:
    fk = e["first_kol"]
    print(fk["name"], "scouted", e["token_symbol"], f"(scout_score={fk['scout_score']}%)")

# Webhook subscription (Ultra) — HMAC-signed push
res = client.rest.first_touch_subscriptions_create(
    name="S-tier scouts on pump tokens",
    filters={"min_scout_tier": "S", "mint_suffix": "pump"},
    delivery_mode="webhook",
    webhook_url="https://you.com/hooks/scout",
)
# store res["webhook_secret"] — shown ONCE
```

CRUD: `first_touch_subscriptions_list()`, `first_touch_subscriptions_get(id)`, `first_touch_subscriptions_update(id, **fields)`, `first_touch_subscriptions_delete(id)`. ULTRA only — up to 10 active.

> **Don't poll — push.** Median lead time before the second KOL is **12 seconds**. WebSocket channel: `kol:first_touches` (PRO+).

### Price Alerts *(new in 1.9)*

CRUD for token dip/recovery price alerts. Fires via WebSocket (`price_alert:events` channel) and/or HMAC-signed webhook when a token's market cap crosses your threshold. PRO=5 rules, ULTRA=25.

```python
res = client.rest.price_alerts_create(
    name="SOL dip buy",
    token_mint="So11111111111111111111111111111111111111112",
    condition="below",          # "below" | "above"
    threshold_mc_usd=5_000_000_000,
    cooldown_min=120,
    delivery_mode="both",
    webhook_url="https://you.com/hooks/price",
)
# store res["webhook_secret"] — shown ONCE
```

`price_alerts_list()`, `price_alerts_get(id)`, `price_alerts_update(id, **fields)`, `price_alerts_delete(id)`.

LangChain: `MadeOnSolPriceAlertsListTool`, `MadeOnSolPriceAlertsCreateTool`. CrewAI: same names via `ALL_TOOLS`.

### Scout Leaderboard & KOL Consensus *(new in 1.9)*

| Method | Tier | Description |
|---|---|---|
| `rest.scout_leaderboard(period=, limit=)` | PRO+ | Top scout-tier KOLs ranked by first-touch follow-on rate, win rate, and ROI |
| `rest.kol_consensus(min_kols=, period=)` | PRO+ | Tokens with the strongest KOL agreement signal — weighted by scout score and recent PnL |
| `rest.peak_history(mint)` | PRO+ | Historical peak-density windows for a token — every coordination spike with KOL breakdown |
| `rest.almost_bonded(min_progress=, min_velocity_pct_per_min=, deployer_tier=, sort=, limit=)` | **New 1.18** · PRO+ | Pre-bond pump.fun tokens near graduation, ranked by velocity (Δprogress/min) — progress_pct, velocity_pct_per_min, eta_minutes, stalled, deployer_tier |
| `rest.coordination_history(period=, limit=)` | PRO+ | Global coordination event log with token, KOL count, score, and outcome |

```python
leaders = client.rest.scout_leaderboard(period="30d", limit=25)
consensus = client.rest.kol_consensus(min_kols=5, period="24h")
```

### Wallet Derived Stats *(new in 1.9)*

`wallet_stats(address)` now includes a `stats` object with derived fields computed from the 90-day trade window:

```python
data = client.rest.wallet_stats("WALLET_ADDRESS")
s = data["stats"]
# s["win_rate"]      — fraction 0-1, tokens sold above cost basis
# s["roi"]           — aggregate return on invested SOL
# s["verdict"]       — "strong" | "profitable" | "neutral" | "losing"
# s["biggest_miss"]  — token with the highest post-exit gain the wallet missed
```

### Copy-Trade Rules (PRO/ULTRA)

Server-side rules that fire signals when one of your watched source wallets trades. Delivered via webhook (HMAC-signed) and/or WebSocket. PRO=3 rules × 5 source wallets each; ULTRA=20 × 50.

| Method | Description |
|---|---|
| `rest.copy_trade_list()` | List your rules |
| `rest.copy_trade_create(source_wallets, sizing_amount, ...)` | Create a rule. Returns `webhook_secret` **once** — store it |
| `rest.copy_trade_get(id)` | Get one rule |
| `rest.copy_trade_update(id, **fields)` | Update fields or toggle `is_active` |
| `rest.copy_trade_delete(id)` | Delete permanently |
| `rest.copy_trade_signals(subscription_id=, since=, limit=)` | Recent fired signals (up to 7 days, 1–500) |

### Wallet Tracker

| Method | Description |
|---|---|
| `rest.wallet_tracker_watchlist()` | List tracked wallets and remaining capacity (Free: 10, Pro: 50, Ultra: 100) |
| `rest.wallet_tracker_add(wallet_address, label=)` | Add wallet to watchlist |
| `rest.wallet_tracker_remove(wallet_address)` | Remove wallet from watchlist |
| `rest.wallet_tracker_update_label(wallet_address, label)` | Update wallet label |
| `rest.wallet_tracker_trades(wallet=, action=, event_type=, limit=, before=)` | Historical swap/transfer events (120-day retention) |
| `rest.wallet_tracker_summary(period=, wallet=)` | Per-wallet stats: swap counts, SOL bought/sold, last event |

### Universal Wallet API *(new in 1.8)*

Per-wallet endpoints that work on **any** Solana wallet, not just curated KOLs. FIFO cost-basis PnL over the last 90 days. PRO+ on every endpoint. Cache hits don't count against your daily quota.

| Method | Description |
|---|---|
| `rest.wallet_stats(address)` | Aggregate stats over 90d + cross-product flags (is_kol + kol_name, is_alpha_tracked + bot_confidence `'none'`/`'low'`/`'medium'`/`'high'`, is_deployer + tokens_deployed; **new 1.22:** is_sniper / is_bundler / is_dumper + `dump_cluster`) |
| `rest.wallet_batch_classify(wallets)` | **New 1.22** · Bulk reputation flags for 1–100 wallets in one call — is_sniper/is_bundler/is_dumper/is_kol, bot_confidence, dump_cluster. Pump.fun-pipeline scoped: `False` = not observed, not verified clean |
| `rest.wallet_pnl(address)` | Full FIFO cost-basis PnL: realized + unrealized SOL, profit factor, max drawdown, avg + median hold minutes, daily UTC PnL curve, closed positions sorted by pnl desc, open positions with live unrealized from mc-tracker |
| `rest.wallet_positions(address)` | Open lots only — shares /pnl cache, lighter response |
| `rest.wallet_trades(address, limit=, cursor=, action=, token_mint=, since=, until=)` | Cursor-paginated raw trades. Default window: last 90 days. limit 1-500 |

**Cost-basis honesty**: observable only inside the 90-day data window. Overflow sells (no matching buy in window) are silently discarded rather than fabricated. `notes.cost_basis_observable_from` makes the cutoff visible per call.

### Webhooks + Streaming

| Method | Description |
|---|---|
| `rest.create_webhook(url, events, filters=)` | Register webhook. Returns `secret` once — store it for HMAC verification |
| `rest.list_webhooks()` | List your webhooks |
| `rest.get_webhook(id)` | Get one + recent delivery log |
| `rest.update_webhook(id, **kwargs)` | Update URL, events, filters, or re-enable |
| `rest.delete_webhook(id)` | Delete permanently |
| `rest.test_webhook(id)` | Send test payload |
| `rest.get_stream_token(rotate=False)` | Issue your WebSocket streaming token (returns `ws_url` + `dex_ws_url`). **Never expires** (1.27.1) — same token on every call; `rotate=True` replaces it (old value works 60 s more). `expires_at` / `next_refresh_at` are always `None` |
| `rest.stream_sessions()` | **New 1.19** · PRO+ · List your live WebSocket sessions (`id`, `service`, `tier`, `channels`, `connected_at`, `remote_ip`, `messages_sent`) across both stream services |
| `rest.kill_stream_session(id)` | **New 1.19** · PRO+ · Force-terminate one of your sessions by `id` and free its slot — self-serve fix for a 4002 connection-limit lockout |

### Rate-limit headers

Every successful REST response captures rate-limit headers in `rest.last_rate_limit`:

```python
client.rest.alpha_leaderboard()
rl = client.rest.last_rate_limit
# {'limit': 100, 'remaining': 92, 'reset': 1714000000, 'request_id': 'rid_abc123'}
if rl['remaining'] is not None and rl['remaining'] < 5:
    print(f"Throttle warning — {rl['remaining']}/{rl['limit']} requests left")
```

### DEX Firehose (Ultra) — WebSocket

`rest.get_stream_token()` returns `dex_ws_url` (Ultra only). Connect with any WebSocket client (`websockets`, `websocket-client`, etc.) and use the multi-subscription protocol — up to **10 named subs per connection**, each with its own `sub_id`, server-side filters, and optional replay (up to 500 most recent matching trades) from a server-side buffer holding ~5 minutes of firehose history — it backfills trades from before your connection existed. Replayed trades arrive newest-first flagged `"replay": true`, then a `replay_done` frame; sort by `block_time` client-side.

```python
import asyncio, json, websockets
from madeonsol_x402 import MadeOnSolClient

client = MadeOnSolClient(api_key="msk_...")

async def main():
    token = client.rest.get_stream_token()  # {"token", "ws_url", "dex_ws_url", ...}

    # token MUST be appended as query param
    async with websockets.connect(f"{token['dex_ws_url']}?token={token['token']}") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "sub_id": "fresh-pumpfun",
            "replay": 50,                       # up to 500 from ring buffer
            "filters": {
                "dex": "pumpfun",
                "token_age_max_seconds": 300,
                "min_sol": 0.5,
                "action": "buy",
            },
        }))

        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("channel") == "dex:trades":
                d = msg["data"]
                print(msg["sub_id"], d["dex"], d["action"], d["sol_amount"])

asyncio.run(main())
```

**Operations** (all carry `sub_id`): `subscribe`, `update` (replace filters in place), `unsubscribe`, `list`, `ping`. **Filters:** `token_mint(s)` (≤50), `wallet(s)` (≤50), `dex` (`pumpfun` | `pumpamm` | `pumpswap` | `raydium` | `jupiter` | `orca` | `meteora` | `launchlab`), `program`, `deployer_tier`, `token_age_max_seconds`, `market_cap_min/max_sol`, `min_sol`, `max_sol`, `action`. At least one targeting filter is required. Inbound rate limit: 5 messages/sec.

Full protocol reference: [madeonsol.com/api-docs#streaming](https://madeonsol.com/api-docs#streaming).

## Tiers

| Tier | Price | Wallets tracked | Requests/day |
|------|-------|-----------------|--------------|
| BASIC (free) | $0 | 10 | 200 |
| PRO | €43/mo (€430/yr) ≈ $49 | 50 | 10,000 |
| ULTRA | €131/mo (€1310/yr) ≈ $149 | 100 + WS events | 100,000 |
| BUSINESS | €400/mo (€4000/yr) ≈ $449 | 500 + WS events | 500,000 |

Free tier returns the full REST response shape on 40+ endpoints — real wallets, TX signatures, full precision — with live feeds delayed 5 minutes (delayed responses carry `delay`/`as_of` and an `X-Data-Delay` header). Paid tiers are real-time and unlock webhooks, WebSockets, rule engines, and ULTRA-only data depth; x402 pay-per-call is always real-time. Get a key at [madeonsol.com/pricing](https://madeonsol.com/pricing).

## Also Available

| Platform | Package |
|---|---|
| TypeScript SDK | [`madeonsol`](https://www.npmjs.com/package/madeonsol) on npm |
| Rust SDK | [`madeonsol`](https://crates.io/crates/madeonsol) on crates.io |
| MCP Server (Claude, Cursor) | [`mcp-server-madeonsol`](https://www.npmjs.com/package/mcp-server-madeonsol) · [Smithery](https://smithery.ai/servers/madeonsol/solana-kol-intelligence) · [Glama](https://glama.ai/mcp/servers/madeonsol/mcp-server-madeonsol) |
| ElizaOS | [`@madeonsol/plugin-madeonsol`](https://www.npmjs.com/package/@madeonsol/plugin-madeonsol) |
| Solana Agent Kit | [`solana-agent-kit-plugin-madeonsol`](https://www.npmjs.com/package/solana-agent-kit-plugin-madeonsol) |

## License

MIT
