"""
Drift Protocol Perpetual Trading Bot — Performance Dashboard
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import timedelta
import numpy as np

# ───────────────────── Page Config ─────────────────────
st.set_page_config(
    page_title="Drift Perp Trader Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────── Constants ─────────────────────
TRADES_FILE = Path(__file__).resolve().parent.parent / "trades.csv"
EXPECTED_COLS = [
    "timestamp", "symbol", "market_index", "market_type", "side",
    "order_type", "price", "quantity", "fee", "slippage_bps",
    "sl", "tp", "pnl", "unrealized_pnl", "status", "duration_seconds",
    "account_equity", "leverage", "sub_account_id", "strategy_id",
    "signal_confidence", "signal_type", "tx_signature", "slot",
    "block_time", "oracle_price_at_entry", "execution_latency_ms",
    "bot_version", "env", "funding_paid", "cumulative_funding",
    "entry_hold_minutes", "taker_fee_rate", "maker_fee_rate",
    "net_pnl_after_fees",
]


# ───────────────────── Data Loading ─────────────────────
@st.cache_data(ttl=30)
def load_trades(path: Path) -> pd.DataFrame:
    """Load and validate trades CSV."""
    df = pd.read_csv(path)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = None
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    # Compute notional value
    df["notional"] = df["price"] * df["quantity"]
    return df


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


# ───────────────────── Sidebar ─────────────────────
st.sidebar.title("🔧 Controls")

# Allow file upload — primary method on Cloud, optional locally
uploaded = st.sidebar.file_uploader("Upload trades.csv", type=["csv"])
if uploaded is not None:
    df = pd.read_csv(uploaded)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = None
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["notional"] = df["price"] * df["quantity"]
elif TRADES_FILE.exists():
    df = load_trades(TRADES_FILE)
else:
    st.warning("⬆️ Upload your **trades.csv** file in the sidebar to get started.")
    st.info("The dashboard reads the 35-column CSV produced by the Drift trading bot.")
    st.stop()

# Date range filter
min_date = df["timestamp"].min().date()
max_date = df["timestamp"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0], tz="UTC"), pd.Timestamp(date_range[1], tz="UTC") + timedelta(days=1)
    df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]

# Side filter
side_filter = st.sidebar.multiselect("Trade side", options=df["side"].dropna().unique().tolist(), default=df["side"].dropna().unique().tolist())
df = df[df["side"].isin(side_filter)]

# Environment filter
env_opts = df["env"].dropna().unique().tolist()
if env_opts:
    env_filter = st.sidebar.multiselect("Environment", options=env_opts, default=env_opts)
    df = df[df["env"].isin(env_filter)]

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
if auto_refresh:
    st.sidebar.info("Dashboard refreshes every 30 seconds.")
    # Streamlit re-runs the script; cache ttl=30 handles freshness

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df)}** trades")


# ───────────────────── Derived Data ─────────────────────
closes = df[df["side"] == "CLOSE"].copy()
entries = df[df["side"].isin(["BUY", "SELL"])].copy()
closes["pnl_clean"] = _safe_float(closes["pnl"])
closes["net_pnl_clean"] = _safe_float(closes["net_pnl_after_fees"])
closes["fee_clean"] = _safe_float(closes["fee"])
closes["funding_clean"] = _safe_float(closes["funding_paid"])
closes["hold_mins"] = _safe_float(closes["entry_hold_minutes"])


# ───────────────────── Header ─────────────────────
st.title("📊 Drift Perp Trader — Dashboard")
st.caption(f"BTC-PERP · MACD Momentum · Devnet  |  Data range: {min_date} → {max_date}")

# ───────────────────── KPI Row ─────────────────────
total_trades = len(df)
total_closes = len(closes)
wins = (closes["net_pnl_clean"] > 0).sum()
losses = (closes["net_pnl_clean"] <= 0).sum()
win_rate = (wins / total_closes * 100) if total_closes else 0

gross_pnl = closes["pnl_clean"].sum()
net_pnl = closes["net_pnl_clean"].sum()
total_fees = _safe_float(df["fee"]).sum()
total_funding = closes["funding_clean"].sum()

avg_win = closes.loc[closes["net_pnl_clean"] > 0, "net_pnl_clean"].mean() if wins > 0 else 0
avg_loss = closes.loc[closes["net_pnl_clean"] <= 0, "net_pnl_clean"].mean() if losses > 0 else 0
profit_factor = abs(avg_win * wins / (avg_loss * losses)) if (losses > 0 and avg_loss != 0) else float("inf")
expectancy = (win_rate / 100 * avg_win + (1 - win_rate / 100) * avg_loss) if total_closes else 0

# Latest equity
latest_equity = _safe_float(df["account_equity"]).iloc[-1] if len(df) else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Trades", total_trades)
k2.metric("Closed Trades", total_closes)
k3.metric("Win Rate", f"{win_rate:.1f}%")
k4.metric("Net PnL", f"${net_pnl:,.2f}", delta=f"${net_pnl:,.2f}")
k5.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float("inf") else "∞")
k6.metric("Account Equity", f"${latest_equity:,.2f}")

k7, k8, k9, k10, k11, k12 = st.columns(6)
k7.metric("Gross PnL", f"${gross_pnl:,.2f}")
k8.metric("Total Fees", f"${total_fees:,.2f}")
k9.metric("Total Funding", f"${total_funding:,.2f}")
k10.metric("Avg Win", f"${avg_win:,.2f}")
k11.metric("Avg Loss", f"${avg_loss:,.2f}")
k12.metric("Expectancy", f"${expectancy:,.2f}")

st.divider()

# ─────────────────── Equity & Cumulative PnL ───────────────────
st.subheader("💰 Equity & Cumulative PnL")

col_eq, col_cum = st.columns(2)

with col_eq:
    eq_df = df[df["account_equity"] > 0][["timestamp", "account_equity"]].copy()
    if not eq_df.empty:
        fig_eq = px.area(
            eq_df, x="timestamp", y="account_equity",
            title="Account Equity Over Time",
            labels={"account_equity": "Equity ($)", "timestamp": ""},
        )
        fig_eq.update_traces(line_color="#00d4aa", fillcolor="rgba(0,212,170,0.15)")
        fig_eq.update_layout(height=380, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_eq, use_container_width=True)
    else:
        st.info("No equity data available.")

with col_cum:
    if not closes.empty:
        cum_df = closes[["timestamp", "net_pnl_clean"]].copy()
        cum_df["cumulative_pnl"] = cum_df["net_pnl_clean"].cumsum()
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=cum_df["timestamp"], y=cum_df["cumulative_pnl"],
            mode="lines+markers", name="Cumulative Net PnL",
            line=dict(color="#00d4aa", width=2),
            marker=dict(size=5),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.1)",
        ))
        fig_cum.update_layout(
            title="Cumulative Net PnL (After Fees & Funding)",
            yaxis_title="PnL ($)", height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_cum, use_container_width=True)
    else:
        st.info("No closed trades yet.")

st.divider()

# ─────────────────── PnL Analysis ───────────────────
st.subheader("📈 PnL Analysis")

col_dist, col_waterfall = st.columns(2)

with col_dist:
    if not closes.empty:
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=closes["net_pnl_clean"],
            nbinsx=30,
            marker_color=["#26a69a" if x > 0 else "#ef5350" for x in closes["net_pnl_clean"]],
            name="Net PnL Distribution",
        ))
        fig_dist.update_layout(
            title="PnL Distribution (per Trade)",
            xaxis_title="Net PnL ($)", yaxis_title="Count",
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

with col_waterfall:
    if not closes.empty:
        colors = ["#26a69a" if v > 0 else "#ef5350" for v in closes["net_pnl_clean"]]
        fig_bar = go.Figure(go.Bar(
            x=list(range(1, len(closes) + 1)),
            y=closes["net_pnl_clean"].values,
            marker_color=colors,
            name="Trade PnL",
        ))
        fig_bar.update_layout(
            title="Per-Trade Net PnL (Chronological)",
            xaxis_title="Trade #", yaxis_title="Net PnL ($)",
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# PnL breakdown: gross vs fees vs funding
col_break, col_scatter = st.columns(2)

with col_break:
    if not closes.empty:
        breakdown = pd.DataFrame({
            "Category": ["Gross PnL", "Fees Paid", "Funding Paid", "Net PnL"],
            "Amount": [gross_pnl, -total_fees, -total_funding, net_pnl],
        })
        fig_break = px.bar(
            breakdown, x="Category", y="Amount",
            color="Category",
            color_discrete_map={
                "Gross PnL": "#42a5f5",
                "Fees Paid": "#ef5350",
                "Funding Paid": "#ffa726",
                "Net PnL": "#26a69a",
            },
            title="PnL Breakdown: Gross → Net",
        )
        fig_break.update_layout(
            height=380, template="plotly_dark", showlegend=False,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_break, use_container_width=True)

with col_scatter:
    if not closes.empty and closes["hold_mins"].sum() > 0:
        fig_hold = px.scatter(
            closes, x="hold_mins", y="net_pnl_clean",
            color=closes["net_pnl_clean"].apply(lambda x: "Win" if x > 0 else "Loss"),
            color_discrete_map={"Win": "#26a69a", "Loss": "#ef5350"},
            size=closes["notional"].abs().clip(lower=1),
            title="PnL vs Hold Time",
            labels={"hold_mins": "Hold Time (min)", "net_pnl_clean": "Net PnL ($)", "color": ""},
        )
        fig_hold.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_hold, use_container_width=True)
    else:
        st.info("No hold-time data available.")

st.divider()

# ─────────────────── Drawdown Analysis ───────────────────
st.subheader("📉 Drawdown Analysis")

if not closes.empty:
    cum_pnl = closes["net_pnl_clean"].cumsum()
    running_max = cum_pnl.cummax()
    drawdown = cum_pnl - running_max

    col_dd, col_streak = st.columns(2)

    with col_dd:
        dd_df = pd.DataFrame({
            "timestamp": closes["timestamp"].values,
            "Cumulative PnL": cum_pnl.values,
            "Peak": running_max.values,
            "Drawdown": drawdown.values,
        })
        fig_dd = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4],
                               vertical_spacing=0.08)
        fig_dd.add_trace(go.Scatter(
            x=dd_df["timestamp"], y=dd_df["Cumulative PnL"],
            mode="lines", name="Cumulative PnL", line=dict(color="#42a5f5", width=2),
        ), row=1, col=1)
        fig_dd.add_trace(go.Scatter(
            x=dd_df["timestamp"], y=dd_df["Peak"],
            mode="lines", name="Peak", line=dict(color="#ffa726", width=1, dash="dot"),
        ), row=1, col=1)
        fig_dd.add_trace(go.Scatter(
            x=dd_df["timestamp"], y=dd_df["Drawdown"],
            mode="lines", name="Drawdown", fill="tozeroy",
            line=dict(color="#ef5350", width=1), fillcolor="rgba(239,83,80,0.3)",
        ), row=2, col=1)
        fig_dd.update_layout(
            title="Cumulative PnL & Drawdown", height=450, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        fig_dd.update_yaxes(title_text="PnL ($)", row=1, col=1)
        fig_dd.update_yaxes(title_text="Drawdown ($)", row=2, col=1)
        st.plotly_chart(fig_dd, use_container_width=True)

    with col_streak:
        max_dd = drawdown.min()
        max_dd_idx = drawdown.idxmin()
        max_dd_ts = closes.loc[max_dd_idx, "timestamp"] if max_dd_idx in closes.index else "N/A"

        # Win/loss streaks
        results = (closes["net_pnl_clean"] > 0).astype(int)
        streaks = results.groupby((results != results.shift()).cumsum())
        win_streaks = [len(g) for _, g in streaks if g.iloc[0] == 1]
        loss_streaks = [len(g) for _, g in streaks if g.iloc[0] == 0]

        s1, s2 = st.columns(2)
        s1.metric("Max Drawdown", f"${max_dd:,.2f}")
        s2.metric("Max DD Date", str(max_dd_ts)[:10] if max_dd_ts != "N/A" else "N/A")

        s3, s4 = st.columns(2)
        s3.metric("Best Win Streak", max(win_streaks) if win_streaks else 0)
        s4.metric("Worst Loss Streak", max(loss_streaks) if loss_streaks else 0)

        s5, s6 = st.columns(2)
        s5.metric("Best Trade", f"${closes['net_pnl_clean'].max():,.2f}")
        s6.metric("Worst Trade", f"${closes['net_pnl_clean'].min():,.2f}")

        # Monthly PnL heatmap
        monthly = closes.copy()
        monthly["month"] = monthly["timestamp"].dt.to_period("M").astype(str)
        monthly_pnl = monthly.groupby("month")["net_pnl_clean"].sum().reset_index()
        if not monthly_pnl.empty:
            fig_monthly = px.bar(
                monthly_pnl, x="month", y="net_pnl_clean",
                color=monthly_pnl["net_pnl_clean"].apply(lambda x: "Profit" if x > 0 else "Loss"),
                color_discrete_map={"Profit": "#26a69a", "Loss": "#ef5350"},
                title="Monthly Net PnL",
                labels={"month": "", "net_pnl_clean": "PnL ($)", "color": ""},
            )
            fig_monthly.update_layout(
                height=220, template="plotly_dark", showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

else:
    st.info("No closed trades to analyze.")

st.divider()

# ─────────────────── Execution Quality ───────────────────
st.subheader("⚡ Execution Quality")

col_lat, col_slip = st.columns(2)

with col_lat:
    lat_df = df[_safe_float(df["execution_latency_ms"]) > 0].copy()
    lat_df["latency"] = _safe_float(lat_df["execution_latency_ms"])
    if not lat_df.empty:
        fig_lat = px.histogram(
            lat_df, x="latency", nbins=25,
            title="Execution Latency Distribution",
            labels={"latency": "Latency (ms)"},
            color_discrete_sequence=["#42a5f5"],
        )
        fig_lat.update_layout(
            height=350, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_lat, use_container_width=True)

        l1, l2, l3 = st.columns(3)
        l1.metric("Avg Latency", f"{lat_df['latency'].mean():.0f} ms")
        l2.metric("P95 Latency", f"{lat_df['latency'].quantile(0.95):.0f} ms")
        l3.metric("Max Latency", f"{lat_df['latency'].max():.0f} ms")
    else:
        st.info("No latency data.")

with col_slip:
    slip_df = df.copy()
    slip_df["slip"] = _safe_float(slip_df["slippage_bps"])
    if slip_df["slip"].sum() > 0:
        fig_slip = px.histogram(
            slip_df, x="slip", nbins=20,
            title="Slippage Distribution (bps)",
            labels={"slip": "Slippage (bps)"},
            color_discrete_sequence=["#ffa726"],
        )
        fig_slip.update_layout(
            height=350, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_slip, use_container_width=True)

        sl1, sl2, sl3 = st.columns(3)
        sl1.metric("Avg Slippage", f"{slip_df['slip'].mean():.1f} bps")
        sl2.metric("Max Slippage", f"{slip_df['slip'].max():.1f} bps")
        sl3.metric("Total Slippage Cost", f"${(slip_df['slip'] / 10000 * slip_df['notional']).sum():,.2f}")
    else:
        st.info("No slippage data.")

st.divider()

# ─────────────────── Position & Risk ───────────────────
st.subheader("🛡️ Position & Risk")

col_size, col_lev = st.columns(2)

with col_size:
    if not entries.empty:
        entries_copy = entries.copy()
        entries_copy["notional_val"] = _safe_float(entries_copy["price"]) * _safe_float(entries_copy["quantity"])
        fig_size = px.scatter(
            entries_copy, x="timestamp", y="notional_val",
            color="side",
            color_discrete_map={"BUY": "#26a69a", "SELL": "#ef5350"},
            size="notional_val",
            title="Position Size Over Time",
            labels={"notional_val": "Notional ($)", "timestamp": ""},
        )
        fig_size.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_size, use_container_width=True)

with col_lev:
    lev_df = df[_safe_float(df["leverage"]) > 0].copy()
    lev_df["lev"] = _safe_float(lev_df["leverage"])
    if not lev_df.empty:
        fig_lev = px.line(
            lev_df, x="timestamp", y="lev",
            title="Leverage Used Over Time",
            labels={"lev": "Leverage (x)", "timestamp": ""},
        )
        fig_lev.update_traces(line_color="#ffa726")
        fig_lev.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_lev, use_container_width=True)
    else:
        st.info("No leverage data.")

# SL/TP analysis
col_sltp, col_rr = st.columns(2)

with col_sltp:
    sl_tp_df = entries.copy()
    sl_tp_df["sl_val"] = _safe_float(sl_tp_df["sl"])
    sl_tp_df["tp_val"] = _safe_float(sl_tp_df["tp"])
    has_sl_tp = sl_tp_df[(sl_tp_df["sl_val"] > 0) | (sl_tp_df["tp_val"] > 0)]
    if not has_sl_tp.empty:
        fig_sltp = go.Figure()
        fig_sltp.add_trace(go.Scatter(
            x=has_sl_tp["timestamp"], y=has_sl_tp["price"],
            mode="markers", name="Entry Price", marker=dict(color="#42a5f5", size=8),
        ))
        fig_sltp.add_trace(go.Scatter(
            x=has_sl_tp["timestamp"], y=has_sl_tp["sl_val"],
            mode="markers", name="Stop Loss", marker=dict(color="#ef5350", size=6, symbol="triangle-down"),
        ))
        fig_sltp.add_trace(go.Scatter(
            x=has_sl_tp["timestamp"], y=has_sl_tp["tp_val"],
            mode="markers", name="Take Profit", marker=dict(color="#26a69a", size=6, symbol="triangle-up"),
        ))
        fig_sltp.update_layout(
            title="Entry Prices with SL/TP Levels",
            yaxis_title="Price ($)", height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_sltp, use_container_width=True)
    else:
        st.info("No SL/TP data available.")

with col_rr:
    # Risk-reward ratio per entry
    rr_df = entries.copy()
    rr_df["sl_val"] = _safe_float(rr_df["sl"])
    rr_df["tp_val"] = _safe_float(rr_df["tp"])
    rr_df["risk"] = (rr_df["price"] - rr_df["sl_val"]).abs()
    rr_df["reward"] = (rr_df["tp_val"] - rr_df["price"]).abs()
    rr_df = rr_df[(rr_df["risk"] > 0) & (rr_df["reward"] > 0)]
    if not rr_df.empty:
        rr_df["rr_ratio"] = rr_df["reward"] / rr_df["risk"]
        fig_rr = px.bar(
            rr_df.reset_index(drop=True), y="rr_ratio",
            title="Risk/Reward Ratio per Entry",
            labels={"rr_ratio": "R:R Ratio", "index": "Trade #"},
            color="rr_ratio",
            color_continuous_scale=["#ef5350", "#ffa726", "#26a69a"],
        )
        fig_rr.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_rr, use_container_width=True)

        avg_rr = rr_df["rr_ratio"].mean()
        st.caption(f"Average Risk/Reward: **{avg_rr:.2f}**")
    else:
        st.info("No valid SL/TP entries for R:R calculation.")

st.divider()

# ─────────────────── Strategy Signal Analysis ───────────────────
st.subheader("🧠 Strategy Signal Analysis")

col_conf, col_sig = st.columns(2)

with col_conf:
    conf_df = closes.copy()
    conf_df["confidence"] = _safe_float(conf_df["signal_confidence"])
    conf_valid = conf_df[conf_df["confidence"] > 0]
    if not conf_valid.empty:
        fig_conf = px.scatter(
            conf_valid, x="confidence", y="net_pnl_clean",
            color=conf_valid["net_pnl_clean"].apply(lambda x: "Win" if x > 0 else "Loss"),
            color_discrete_map={"Win": "#26a69a", "Loss": "#ef5350"},
            title="Signal Confidence vs PnL",
            labels={"confidence": "Signal Confidence", "net_pnl_clean": "Net PnL ($)", "color": ""},
        )
        fig_conf.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_conf, use_container_width=True)
    else:
        st.info("No signal confidence data.")

with col_sig:
    sig_type_df = closes.copy()
    sig_type_df["sig"] = sig_type_df["signal_type"].fillna("unknown")
    sig_summary = sig_type_df.groupby("sig").agg(
        count=("net_pnl_clean", "count"),
        total_pnl=("net_pnl_clean", "sum"),
        avg_pnl=("net_pnl_clean", "mean"),
        win_rate=("net_pnl_clean", lambda x: (x > 0).mean() * 100),
    ).reset_index()
    if not sig_summary.empty:
        fig_sig = px.bar(
            sig_summary, x="sig", y="total_pnl",
            color="win_rate",
            color_continuous_scale=["#ef5350", "#ffa726", "#26a69a"],
            title="PnL by Signal Type",
            labels={"sig": "Signal Type", "total_pnl": "Total PnL ($)", "win_rate": "Win Rate %"},
            text="count",
        )
        fig_sig.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_sig, use_container_width=True)

st.divider()

# ─────────────────── Funding & Fee Details ───────────────────
st.subheader("💸 Costs Breakdown")

col_fee_t, col_fund_t = st.columns(2)

with col_fee_t:
    fee_ts = df[_safe_float(df["fee"]) > 0].copy()
    fee_ts["fee_val"] = _safe_float(fee_ts["fee"])
    if not fee_ts.empty:
        fig_fee = px.bar(
            fee_ts, x="timestamp", y="fee_val",
            color="side",
            color_discrete_map={"BUY": "#42a5f5", "SELL": "#ef5350", "CLOSE": "#ffa726"},
            title="Fees Per Trade",
            labels={"fee_val": "Fee ($)", "timestamp": ""},
        )
        fig_fee.update_layout(
            height=350, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_fee, use_container_width=True)
    else:
        st.info("No fee data.")

with col_fund_t:
    fund_ts = closes.copy()
    fund_ts["fund_val"] = _safe_float(fund_ts["funding_paid"])
    fund_valid = fund_ts[fund_ts["fund_val"].abs() > 0]
    if not fund_valid.empty:
        fig_fund = px.bar(
            fund_valid, x="timestamp", y="fund_val",
            title="Funding Paid Per Close",
            labels={"fund_val": "Funding ($)", "timestamp": ""},
            color=fund_valid["fund_val"].apply(lambda x: "Paid" if x > 0 else "Received"),
            color_discrete_map={"Paid": "#ef5350", "Received": "#26a69a"},
        )
        fig_fund.update_layout(
            height=350, template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_fund, use_container_width=True)
    else:
        st.info("No funding data.")

# Cumulative costs
if not closes.empty:
    cum_fee = _safe_float(df["fee"]).cumsum()
    cum_fund = closes["funding_clean"].cumsum()
    fig_cum_cost = go.Figure()
    fig_cum_cost.add_trace(go.Scatter(
        x=df["timestamp"], y=cum_fee, mode="lines", name="Cumulative Fees",
        line=dict(color="#ef5350", width=2),
    ))
    fig_cum_cost.add_trace(go.Scatter(
        x=closes["timestamp"], y=cum_fund, mode="lines", name="Cumulative Funding",
        line=dict(color="#ffa726", width=2),
    ))
    fig_cum_cost.update_layout(
        title="Cumulative Trading Costs", yaxis_title="Cost ($)",
        height=320, template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_cum_cost, use_container_width=True)

st.divider()

# ─────────────────── Full Trade Log ───────────────────
st.subheader("📋 Trade Log")

display_cols = [
    "timestamp", "side", "price", "quantity", "notional",
    "fee", "pnl", "net_pnl_after_fees", "funding_paid",
    "sl", "tp", "entry_hold_minutes", "leverage",
    "signal_confidence", "status", "tx_signature",
]
display_df = df[[c for c in display_cols if c in df.columns]].copy()
display_df = display_df.sort_values("timestamp", ascending=False)

# Format for display
format_map = {
    "price": "${:,.2f}",
    "quantity": "{:.6f}",
    "notional": "${:,.2f}",
    "fee": "${:,.4f}",
    "pnl": "${:,.2f}",
    "net_pnl_after_fees": "${:,.2f}",
    "funding_paid": "${:,.4f}",
    "sl": "${:,.2f}",
    "tp": "${:,.2f}",
    "entry_hold_minutes": "{:.0f}",
    "leverage": "{:.1f}x",
    "signal_confidence": "{:.2f}",
}

def highlight_side(row):
    """Color rows by trade side."""
    color_map = {"BUY": "background-color: rgba(38,166,154,0.15)",
                 "SELL": "background-color: rgba(239,83,80,0.15)",
                 "CLOSE": "background-color: rgba(255,167,38,0.15)"}
    return [color_map.get(row.get("side", ""), "")] * len(row)

styled = display_df.style.apply(highlight_side, axis=1)
for col, fmt in format_map.items():
    if col in display_df.columns:
        styled = styled.format({col: fmt}, na_rep="—")

st.dataframe(styled, use_container_width=True, height=500)

# Download button
csv_data = df.to_csv(index=False)
st.download_button(
    "⬇️ Download Full Trade Data (CSV)",
    csv_data,
    file_name="drift_trades_export.csv",
    mime="text/csv",
)

st.divider()

# ─────────────────── Footer ───────────────────
st.caption("Drift Protocol Perpetual Trading Bot · MACD Momentum Strategy · Built with Streamlit & Plotly")
