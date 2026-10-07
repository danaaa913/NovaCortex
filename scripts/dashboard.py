import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import os
import re
import json
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

pio.templates.default = "plotly_white"

# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def detect_language(text):
    if not isinstance(text, str): return "unknown"
    ar = len(re.findall(r'[\u0600-\u06FF]', text))
    en = len(re.findall(r'[a-zA-Z]', text))
    if ar == 0 and en == 0: return "unknown"
    return "arabic" if ar >= en else "english"

def pct(part, total):
    return f"{(part/total*100):.1f}%" if total > 0 else "0.0%"

def fmt_ms(ms):
    if ms < 1000: return f"{ms:.0f}ms"
    return f"{ms/1000:.1f}s"

# color palette
C = {
    "teal":   "#00C9A7",
    "blue":   "#4361EE",
    "purple": "#7B2FBE",
    "orange": "#F77F00",
    "red":    "#EF233C",
    "yellow": "#FFD60A",
    "green":  "#52B788",
    "pink":   "#FF6B9D",
    "dark":   "#0D1117",
    "card":   "#161B22",
    "border": "#30363D",
    "text":   "#E6EDF3",
    "muted":  "#8B949E",
}

SOURCE_COLORS = {
    "verified_facts":         C["teal"],
    "rag":                    C["blue"],
    "web":                    C["orange"],
    "cache":                  C["yellow"],
    "llm_fallback":           C["purple"],
    "out_of_scope":           C["red"],
    "injection_blocked":      "#FF0054",
    "false_premise_corrected":"#FF6B9D",
    "comparison_rejected":    "#F77F00",
    "greeting":               C["green"],
    "multi_query":            "#A8DADC",
    "error":                  "#6B0504",
    "unknown":                C["muted"],
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'JetBrains Mono', monospace", color=C["text"], size=11),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=C["border"], borderwidth=1),
    xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
)

def apply_layout(fig, title=""):
    fig.update_layout(**CHART_LAYOUT, title=dict(text=title, font=dict(size=13, color=C["text"])))
    return fig

def fig_to_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})

# ══════════════════════════════════════════════════════════
#  MAIN DASHBOARD
# ══════════════════════════════════════════════════════════

def create_dashboard():
    # ── find DB ──────────────────────────────────────────
    db_candidates = [
        ROOT / "novacortex_v12.db", ROOT / "novacortex_v13.db",
        ROOT / "novacortex_v11.db", ROOT / "novacortex_v10.2.db"
    ]
    db_path = None
    for p in db_candidates:
        if os.path.exists(p):
            db_path = p
            break
    if not db_path:
        print("❌ No database found. Run the bot first.")
        return

    print(f"📂 Using database: {db_path}")
    conn = sqlite3.connect(db_path)

    df_log    = pd.read_sql_query("SELECT * FROM questions_log", conn)
    df_users  = pd.read_sql_query("SELECT * FROM users", conn)
    df_daily  = pd.read_sql_query("SELECT * FROM daily_stats", conn)
    df_cache  = pd.read_sql_query("SELECT * FROM response_cache", conn)
    df_memory = pd.read_sql_query("SELECT * FROM conversation_memory", conn)
    conn.close()

    if df_log.empty:
        print("⚠️  No queries logged yet. Interact with the bot first.")
        return

    # ── parse timestamps ─────────────────────────────────
    df_log['timestamp']     = pd.to_datetime(df_log['timestamp'],    errors='coerce')
    df_users['last_active'] = pd.to_datetime(df_users['last_active'],errors='coerce')
    df_users['created_at']  = pd.to_datetime(df_users['created_at'], errors='coerce')
    df_daily['date']        = pd.to_datetime(df_daily['date'],        errors='coerce')

    # ── clean ─────────────────────────────────────────────
    df_log['source']      = df_log['source'].fillna('unknown')
    df_log['study_level'] = df_log['study_level'].fillna('Unknown')
    df_log['confidence']  = pd.to_numeric(df_log['confidence'],    errors='coerce').fillna(0)
    df_log['response_time_ms'] = pd.to_numeric(df_log['response_time_ms'], errors='coerce').fillna(0)
    if 'docs_retrieved' not in df_log.columns:
        df_log['docs_retrieved'] = 0
    df_log['docs_retrieved'] = pd.to_numeric(df_log['docs_retrieved'], errors='coerce').fillna(0)

    total = len(df_log)

    # ══════════════════════════════════════════════════════
    #  COMPUTE ALL METRICS
    # ══════════════════════════════════════════════════════

    # --- source counts ---
    all_sources = [
        "verified_facts","rag","web","cache","llm_fallback",
        "out_of_scope","injection_blocked","false_premise_corrected",
        "comparison_rejected","greeting","multi_query","error","unknown"
    ]
    sc = {s: int((df_log['source'] == s).sum()) for s in all_sources}

    # --- guardrails ---
    guardrail_srcs = ["out_of_scope","injection_blocked","false_premise_corrected","comparison_rejected"]
    guardrail_total = sum(sc[s] for s in guardrail_srcs)

    # --- pipeline paths ---
    deterministic  = sc["verified_facts"] + sc["cache"]
    rag_count      = sc["rag"]
    web_count      = sc["web"]
    llm_fb_count   = sc["llm_fallback"]
    safe_responses = total - guardrail_total

    # --- KPIs ---
    avg_conf     = df_log['confidence'].mean()
    avg_rt       = df_log['response_time_ms'].mean()
    median_rt    = df_log['response_time_ms'].median()
    error_rate   = sc["error"] / total * 100 if total else 0
    fast_pct     = (df_log['response_time_ms'] < 2000).sum() / total * 100 if total else 0
    high_conf    = (df_log['confidence'] >= 80).sum()
    low_conf     = (df_log['confidence'] < 50).sum()
    cache_hit_rate = (df_daily['cache_hits'].sum() / df_daily['total_queries'].sum() * 100
                      if not df_daily.empty and df_daily['total_queries'].sum() > 0 else 0)
    avg_docs     = df_log[df_log['docs_retrieved'] > 0]['docs_retrieved'].mean() if (df_log['docs_retrieved'] > 0).any() else 0

    # --- users ---
    total_users  = len(df_users)
    now          = datetime.now()
    active_7d    = int((df_users['last_active'] > now - timedelta(days=7)).sum()) if not df_users.empty else 0
    active_24h   = int((df_users['last_active'] > now - timedelta(hours=24)).sum()) if not df_users.empty else 0

    # --- language ---
    df_log['lang'] = df_log['question'].apply(detect_language)
    lang_counts = df_log['lang'].value_counts().to_dict()

    # --- time patterns ---
    df_log['hour']    = df_log['timestamp'].dt.hour
    df_log['weekday'] = df_log['timestamp'].dt.day_name()
    df_log['date']    = df_log['timestamp'].dt.date
    df_log['qlen']    = df_log['question'].apply(lambda x: len(str(x).split()) if isinstance(x, str) else 0)

    # --- memory/cache ---
    total_msgs   = len(df_memory)
    avg_msgs_user= df_memory.groupby('user_id').size().mean() if not df_memory.empty else 0
    summary_rate = (df_memory['is_summary'].sum() / total_msgs * 100) if total_msgs > 0 else 0
    total_cache_entries = len(df_cache)
    avg_cache_hits      = df_cache['hit_count'].mean() if not df_cache.empty else 0


    # ══════════════════════════════════════════════════════
    #  HALLUCINATION RISK ANALYSIS
    # ══════════════════════════════════════════════════════
    HALLUCINATION_RISK = {
        "verified_facts": 0,
        "cache":          0,
        "greeting":       0,
        "out_of_scope":   0,
        "injection_blocked":      0,
        "false_premise_corrected":0,
        "comparison_rejected":    0,
        "multi_query":    5,
        "rag":            15,
        "web":            20,
        "llm_fallback":   45,
        "error":          0,
        "unknown":        30,
    }
    weighted_risk  = sum(sc.get(s,0)*r for s,r in HALLUCINATION_RISK.items())
    hal_risk_score = weighted_risk / total if total > 0 else 0
    if   hal_risk_score < 5:  hal_level = ("🟢 Minimal Risk",  "#00C9A7")
    elif hal_risk_score < 15: hal_level = ("🟡 Low Risk",      "#FFD60A")
    elif hal_risk_score < 30: hal_level = ("🟠 Moderate Risk", "#F77F00")
    else:                     hal_level = ("🔴 High Risk",     "#EF233C")

    low_conf_responses  = int((df_log["confidence"] < 70).sum())
    very_low_conf       = int((df_log["confidence"] < 50).sum())
    high_risk_responses = int((df_log["source"] == "llm_fallback").sum())
    safe_sources = ["verified_facts","cache","out_of_scope","injection_blocked",
                    "false_premise_corrected","comparison_rejected","greeting"]
    safe_count = sum(sc.get(s,0) for s in safe_sources)
    safe_rate  = safe_count / total * 100 if total > 0 else 0

    conf_buckets = {
        "Certain (100%)":   int((df_log["confidence"]==100).sum()),
        "High (80-99%)":    int(((df_log["confidence"]>=80)&(df_log["confidence"]<100)).sum()),
        "Moderate (70-79%)":int(((df_log["confidence"]>=70)&(df_log["confidence"]<80)).sum()),
        "Low (50-69%)":     int(((df_log["confidence"]>=50)&(df_log["confidence"]<70)).sum()),
        "Very Low (<50%)":  int((df_log["confidence"]<50).sum()),
    }
    source_conf_avg = (
        df_log[df_log["source"].isin(["verified_facts","rag","web","cache","llm_fallback"])]
        .groupby("source")["confidence"]
        .agg(["mean","count","std"]).reset_index()
    )
    source_conf_avg.columns = ["source","avg_conf","count","std_conf"]
    source_conf_avg["std_conf"]  = source_conf_avg["std_conf"].fillna(0)
    source_conf_avg["hal_risk%"] = source_conf_avg["source"].map(HALLUCINATION_RISK).fillna(30)

    # --- top questions ---
    top_qs = Counter(df_log['question'].dropna()).most_common(10)


    # ── HALLUCINATION CHARTS ─────────────────────────────

    fig_hal_buckets = go.Figure(go.Bar(
        x=list(conf_buckets.keys()),
        y=list(conf_buckets.values()),
        marker_color=[C["teal"], C["green"], C["yellow"], C["orange"], C["red"]],
        marker_line=dict(color=C["dark"], width=1),
        text=list(conf_buckets.values()),
        textposition="outside",
        textfont=dict(color=C["text"]),
    ))
    apply_layout(fig_hal_buckets, "🎯 Confidence Buckets — How Certain Is The Bot?")
    fig_hal_buckets.add_hline(y=0, line_color=C["border"])

    if not source_conf_avg.empty:
        colors_src = [SOURCE_COLORS.get(s, C["muted"]) for s in source_conf_avg["source"]]
        fig_hal_src = make_subplots(specs=[[{"secondary_y": True}]])
        fig_hal_src.add_trace(go.Bar(
            x=source_conf_avg["source"],
            y=source_conf_avg["avg_conf"],
            name="Avg Confidence %",
            marker_color=colors_src,
            marker_line=dict(color=C["dark"], width=1),
            error_y=dict(type="data", array=source_conf_avg["std_conf"].tolist(),
                         color=C["muted"], thickness=1.5),
        ), secondary_y=False)
        fig_hal_src.add_trace(go.Scatter(
            x=source_conf_avg["source"],
            y=source_conf_avg["hal_risk%"],
            name="Hallucination Risk %",
            mode="lines+markers",
            line=dict(color=C["red"], width=2, dash="dot"),
            marker=dict(size=8, color=C["red"]),
        ), secondary_y=True)
        fig_hal_src.update_layout(**CHART_LAYOUT,
            title=dict(text="⚠️ Confidence vs Hallucination Risk per Source",
                       font=dict(size=13, color=C["text"])))
        fig_hal_src.update_yaxes(title_text="Avg Confidence %", secondary_y=False,
            gridcolor=C["border"], color=C["teal"])
        fig_hal_src.update_yaxes(title_text="Hallucination Risk %", secondary_y=True,
            gridcolor="rgba(0,0,0,0)", color=C["red"], range=[0, 60])
    else:
        fig_hal_src = go.Figure()
        apply_layout(fig_hal_src, "⚠️ Hallucination Risk (no probabilistic data)")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(hal_risk_score, 1),
        title={"text": "Overall Hallucination Risk Score", "font": {"color": C["text"], "size": 13}},
        delta={"reference": 15, "increasing": {"color": C["red"]}, "decreasing": {"color": C["teal"]}},
        gauge={
            "axis": {"range": [0, 50], "tickcolor": C["muted"],
                     "tickfont": {"color": C["muted"]}},
            "bar":  {"color": hal_level[1], "thickness": 0.25},
            "bgcolor": C["card"],
            "bordercolor": C["border"],
            "steps": [
                {"range": [0, 5],   "color": "rgba(0,201,167,0.15)"},
                {"range": [5, 15],  "color": "rgba(255,214,10,0.15)"},
                {"range": [15, 30], "color": "rgba(247,127,0,0.15)"},
                {"range": [30, 50], "color": "rgba(239,35,60,0.15)"},
            ],
            "threshold": {
                "line": {"color": C["red"], "width": 2},
                "thickness": 0.75,
                "value": 15,
            },
        },
        number={"font": {"color": hal_level[1], "size": 36}, "suffix": "/50"},
    ))
    fig_gauge.update_layout(**CHART_LAYOUT,
        title=dict(text=f"🧠 Hallucination Risk Gauge — {hal_level[0]}",
                   font=dict(size=13, color=C["text"])))

    df_low = df_log[df_log["confidence"] < 70].copy()
    df_low["date2"] = df_low["timestamp"].dt.date
    low_over_time = df_low.groupby("date2").size().reset_index(name="low_conf_count")
    all_dates = df_log.groupby("date").size().reset_index(name="total_day")
    all_dates.columns = ["date2","total_day"]
    low_merged = pd.merge(all_dates, low_over_time, on="date2", how="left").fillna(0)
    low_merged["low_conf_pct"] = low_merged["low_conf_count"] / low_merged["total_day"] * 100

    fig_hal_time = go.Figure()
    fig_hal_time.add_trace(go.Scatter(
        x=low_merged["date2"], y=low_merged["low_conf_pct"],
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(239,35,60,0.10)",
        line=dict(color=C["red"], width=2),
        marker=dict(size=5),
        name="Low Conf %",
    ))
    fig_hal_time.add_hline(y=20, line_dash="dash", line_color=C["yellow"],
        annotation_text="20% warning threshold",
        annotation_font_color=C["yellow"])
    apply_layout(fig_hal_time, "📉 Low-Confidence Responses Over Time (Hallucination Trend)")

    # ══════════════════════════════════════════════════════
    #  BUILD CHARTS
    # ══════════════════════════════════════════════════════

    pipeline_labels = ["Total Queries","Guardrails","Safe Responses",
                       "Cache Hit","Verified Facts","RAG","Web","LLM Fallback"]
    pipeline_vals   = [total, -guardrail_total, safe_responses,
                       sc["cache"], sc["verified_facts"], rag_count, web_count, llm_fb_count]
    fig_waterfall = go.Figure(go.Waterfall(
        name="pipeline", orientation="v",
        measure=["absolute","relative","absolute","relative","relative","relative","relative","relative"],
        x=pipeline_labels, y=pipeline_vals,
        connector={"line":{"color":C["border"]}},
        decreasing={"marker":{"color":C["red"]}},
        increasing={"marker":{"color":C["teal"]}},
        totals={"marker":{"color":C["blue"]}},
    ))
    apply_layout(fig_waterfall, "🔀 Query Pipeline Flow")

    src_df = pd.DataFrame([(k,v) for k,v in sc.items() if v>0], columns=["source","count"])
    src_df["color"] = src_df["source"].map(SOURCE_COLORS).fillna(C["muted"])
    fig_sources = go.Figure(go.Pie(
        labels=src_df["source"], values=src_df["count"],
        hole=0.55,
        marker=dict(colors=src_df["color"].tolist(), line=dict(color=C["dark"], width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color=C["text"]),
    ))
    apply_layout(fig_sources, "🎯 Response Source Distribution")
    fig_sources.add_annotation(text=f"<b>{total}</b><br>total", x=0.5, y=0.5,
        font=dict(size=14, color=C["text"]), showarrow=False)

    g_labels = guardrail_srcs + ["safe_response"]
    g_vals   = [sc[s] for s in guardrail_srcs] + [safe_responses]
    g_colors = [SOURCE_COLORS.get(s, C["muted"]) for s in guardrail_srcs] + [C["teal"]]
    fig_guard = go.Figure(go.Pie(
        labels=g_labels, values=g_vals, hole=0.5,
        marker=dict(colors=g_colors, line=dict(color=C["dark"], width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color=C["text"]),
    ))
    apply_layout(fig_guard, f"🛡️ Guardrail System — {pct(guardrail_total, total)} blocked")
    fig_guard.add_annotation(text=f"<b>{guardrail_total}</b><br>blocked", x=0.5, y=0.5,
        font=dict(size=14, color=C["red"]), showarrow=False)

    qt = df_log.groupby('date').size().reset_index(name='count')
    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(
        x=qt['date'], y=qt['count'], mode='lines+markers',
        line=dict(color=C["teal"], width=2),
        fill='tozeroy', fillcolor="rgba(0,201,167,0.10)",
        marker=dict(size=5, color=C["teal"]),
        name="queries"
    ))
    apply_layout(fig_time, "📅 Queries Over Time")

    conf_df = df_log[df_log['source'].isin(["verified_facts","rag","web","cache","llm_fallback"])]
    fig_conf = go.Figure()
    for src in ["verified_facts","rag","web","cache","llm_fallback"]:
        d = conf_df[conf_df['source']==src]['confidence']
        if len(d) > 0:
            fig_conf.add_trace(go.Box(
                y=d, name=src,
                marker_color=SOURCE_COLORS.get(src, C["muted"]),
                line_color=SOURCE_COLORS.get(src, C["muted"]),
                fillcolor="rgba(100,100,100,0.2)",
            ))
    apply_layout(fig_conf, "📊 Confidence Distribution by Source")

    df_s = df_log.sort_values('timestamp').copy()
    df_s['conf_rolling'] = df_s['confidence'].rolling(window=max(5, total//20), min_periods=1).mean()
    df_s['rt_rolling']   = df_s['response_time_ms'].rolling(window=max(5, total//20), min_periods=1).mean()
    fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
    fig_trend.add_trace(go.Scatter(
        x=df_s['timestamp'], y=df_s['conf_rolling'],
        name="Confidence %", line=dict(color=C["teal"], width=2), mode='lines'
    ), secondary_y=False)
    fig_trend.add_trace(go.Scatter(
        x=df_s['timestamp'], y=df_s['rt_rolling'],
        name="Response Time (ms)", line=dict(color=C["orange"], width=2, dash='dot'), mode='lines'
    ), secondary_y=True)
    fig_trend.update_layout(**CHART_LAYOUT, title=dict(text="📈 Confidence & Speed Trends", font=dict(size=13, color=C["text"])))
    fig_trend.update_yaxes(title_text="Confidence %", secondary_y=False,
        gridcolor=C["border"], color=C["teal"])
    fig_trend.update_yaxes(title_text="Response Time (ms)", secondary_y=True,
        gridcolor="rgba(0,0,0,0)", color=C["orange"])

    fig_rt = go.Figure(go.Histogram(
        x=df_log['response_time_ms'], nbinsx=30,
        marker_color=C["blue"], opacity=0.8,
        marker_line=dict(color=C["dark"], width=1),
    ))
    fig_rt.add_vline(x=avg_rt, line_dash="dash", line_color=C["yellow"],
        annotation_text=f"avg {fmt_ms(avg_rt)}", annotation_font_color=C["yellow"])
    fig_rt.add_vline(x=2000, line_dash="dot", line_color=C["red"],
        annotation_text="2s threshold", annotation_font_color=C["red"])
    apply_layout(fig_rt, "⚡ Response Time Distribution")

    weekday_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    heat = df_log.groupby(['weekday','hour']).size().reset_index(name='count')
    heat_pivot = heat.pivot(index='weekday', columns='hour', values='count').fillna(0)
    heat_pivot = heat_pivot.reindex([d for d in weekday_order if d in heat_pivot.index])
    fig_heat = go.Figure(go.Heatmap(
        z=heat_pivot.values,
        x=[f"{h:02d}:00" for h in heat_pivot.columns],
        y=heat_pivot.index.tolist(),
        colorscale=[[0,C["dark"]],[0.5,C["blue"]],[1,C["teal"]]],
        showscale=True,
    ))
    apply_layout(fig_heat, "🕐 Activity Heatmap (Hour × Day)")

    fig_lang = go.Figure(go.Pie(
        labels=list(lang_counts.keys()), values=list(lang_counts.values()),
        hole=0.4,
        marker=dict(
            colors=[C["blue"], C["orange"], C["muted"]],
            line=dict(color=C["dark"], width=2)
        ),
        textinfo="label+percent",
        textfont=dict(size=11, color=C["text"]),
    ))
    apply_layout(fig_lang, "🌐 Query Language Distribution")

    fig_scatter = go.Figure(go.Scatter(
        x=df_log['qlen'], y=df_log['confidence'],
        mode='markers',
        marker=dict(
            color=df_log['response_time_ms'],
            colorscale='Viridis', showscale=True,
            colorbar=dict(title="RT (ms)", tickfont=dict(color=C["text"])),
            size=6, opacity=0.7,
        ),
        text=df_log['source'],
        hovertemplate="Length: %{x}<br>Confidence: %{y}%<br>Source: %{text}<extra></extra>"
    ))
    apply_layout(fig_scatter, "🔬 Query Length vs Confidence (colored by response time)")

    if 'study_level' in df_users.columns and not df_users.empty:
        lvl = df_users['study_level'].value_counts().reset_index()
        lvl.columns = ['level','count']
        fig_level = go.Figure(go.Bar(
            x=lvl['level'], y=lvl['count'],
            marker_color=C["purple"],
            marker_line=dict(color=C["dark"], width=1),
        ))
        apply_layout(fig_level, "🎓 Users by Study Level")
    else:
        fig_level = go.Figure()
        apply_layout(fig_level, "🎓 Users by Study Level (no data)")

    if not df_cache.empty:
        cache_top = df_cache.nlargest(10, 'hit_count')[['question','hit_count','confidence']]
        fig_cache = go.Figure(go.Bar(
            x=cache_top['hit_count'],
            y=[q[:40]+"…" if len(str(q))>40 else str(q) for q in cache_top['question']],
            orientation='h',
            marker_color=C["yellow"],
            marker_line=dict(color=C["dark"], width=1),
        ))
        apply_layout(fig_cache, "⚡ Top 10 Cached Questions (by hits)")
        fig_cache.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig_cache = go.Figure()
        apply_layout(fig_cache, "⚡ Cache (empty)")

    # ══════════════════════════════════════════════════════
    #  BUILD UNIFIED HTML
    # ══════════════════════════════════════════════════════

    charts = {
        "waterfall": fig_to_html(fig_waterfall),
        "sources":   fig_to_html(fig_sources),
        "guard":     fig_to_html(fig_guard),
        "time":      fig_to_html(fig_time),
        "conf":      fig_to_html(fig_conf),
        "trend":     fig_to_html(fig_trend),
        "rt":        fig_to_html(fig_rt),
        "heat":      fig_to_html(fig_heat),
        "lang":      fig_to_html(fig_lang),
        "scatter":   fig_to_html(fig_scatter),
        "level":     fig_to_html(fig_level),
        "cache":     fig_to_html(fig_cache),
        "hal_buckets": fig_to_html(fig_hal_buckets),
        "hal_src":     fig_to_html(fig_hal_src),
        "gauge":       fig_to_html(fig_gauge),
        "hal_time":    fig_to_html(fig_hal_time),
    }

    def kpi(icon, label, value, sub="", color=C["teal"]):
        return f"""
        <div class="kpi-card">
          <div class="kpi-icon" style="color:{color}">{icon}</div>
          <div class="kpi-value" style="color:{color}">{value}</div>
          <div class="kpi-label">{label}</div>
          {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
        </div>"""

    def section(title, *chart_htmls, cols=2):
        cards = "".join(f'<div class="chart-card">{h}</div>' for h in chart_htmls)
        return f"""
        <section>
          <h2 class="section-title">{title}</h2>
          <div class="charts-grid cols-{cols}">{cards}</div>
        </section>"""

    def table_html(headers, rows, title=""):
        ths = "".join(f"<th>{h}</th>" for h in headers)
        trs = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return f"""
        <div class="chart-card table-card">
          {"<div class='table-title'>"+title+"</div>" if title else ""}
          <div class="table-scroll">
            <table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>
          </div>
        </div>"""

    guardrail_rows_html = [
        [f'<span class="tag" style="background:{SOURCE_COLORS.get(s,C["muted"])}22;color:{SOURCE_COLORS.get(s,C["muted"])};border:1px solid {SOURCE_COLORS.get(s,C["muted"])}44">{s}</span>',
         f'<b>{sc[s]}</b>', pct(sc[s], total)]
        for s in guardrail_srcs
    ] + [[
        '<span class="tag" style="background:rgba(0,201,167,0.13);color:#00C9A7;border:1px solid rgba(0,201,167,0.27)">✅ TOTAL BLOCKED</span>',
        f'<b>{guardrail_total}</b>', f'<b>{pct(guardrail_total, total)}</b>'
    ]]

    top_q_rows_html = [
        [f'<span class="q-num">{i+1}</span>',
         f'<span class="q-text">{str(q)[:70]}{"…" if len(str(q))>70 else ""}</span>',
         f'<span class="q-count">{c}×</span>']
        for i,(q,c) in enumerate(top_qs)
    ]

    source_rows_html = [
        [f'<span class="tag" style="background:{SOURCE_COLORS.get(s,C["muted"])}22;color:{SOURCE_COLORS.get(s,C["muted"])};border:1px solid {SOURCE_COLORS.get(s,C["muted"])}44">{s}</span>',
         f'<b>{v}</b>', pct(v, total)]
        for s,v in sorted(sc.items(), key=lambda x:-x[1]) if v>0
    ]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NovaCortex v13 — Analytics Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:      {C["dark"]};
    --card:    {C["card"]};
    --border:  {C["border"]};
    --text:    {C["text"]};
    --muted:   {C["muted"]};
    --teal:    {C["teal"]};
    --blue:    {C["blue"]};
    --purple:  {C["purple"]};
    --orange:  {C["orange"]};
    --red:     {C["red"]};
    --yellow:  {C["yellow"]};
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse 80% 50% at 20% -10%, rgba(67,97,238,0.15) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 80% 110%, rgba(0,201,167,0.10) 0%, transparent 60%);
  }}

  .header {{
    padding: 40px 48px 32px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
  }}
  .header-left {{ flex: 1; }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border: 1px solid var(--teal);
    color: var(--teal);
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-radius: 3px;
    margin-bottom: 12px;
  }}
  h1 {{
    font-family: 'Syne', sans-serif;
    font-size: 36px;
    font-weight: 800;
    line-height: 1.1;
    background: linear-gradient(135deg, var(--teal) 0%, var(--blue) 50%, var(--purple) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header-meta {{
    margin-top: 10px;
    color: var(--muted);
    font-size: 11px;
    display: flex;
    gap: 20px;
  }}
  .status-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--teal);
    box-shadow: 0 0 8px var(--teal);
    animation: pulse 2s infinite;
  }}
  @keyframes pulse {{
    0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }}
  }}

  .container {{ padding: 0 48px 60px; }}

  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 14px;
    padding: 32px 0;
  }}
  .kpi-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 16px;
    transition: border-color .2s, transform .2s;
  }}
  .kpi-card:hover {{ border-color: var(--teal); transform: translateY(-2px); }}
  .kpi-icon {{ font-size: 20px; margin-bottom: 8px; }}
  .kpi-value {{
    font-family: 'Syne', sans-serif;
    font-size: 26px;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 4px;
  }}
  .kpi-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }}
  .kpi-sub {{ color: var(--muted); font-size: 10px; margin-top: 4px; }}

  section {{ margin-top: 40px; }}
  .section-title {{
    font-family: 'Syne', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .charts-grid {{
    display: grid;
    gap: 14px;
  }}
  .charts-grid.cols-1 {{ grid-template-columns: 1fr; }}
  .charts-grid.cols-2 {{ grid-template-columns: repeat(2, 1fr); }}
  .charts-grid.cols-3 {{ grid-template-columns: repeat(3, 1fr); }}
  .chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    overflow: hidden;
    transition: border-color .2s;
  }}
  .chart-card:hover {{ border-color: var(--blue); }}

  .table-card {{ padding: 20px; }}
  .table-title {{
    font-family: 'Syne', sans-serif;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 14px;
    color: var(--text);
  }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    background: rgba(255,255,255,0.04);
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 9px 12px;
    border-bottom: 1px solid rgba(48,54,61,0.5);
    color: var(--text);
    vertical-align: middle;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255,255,255,0.03); }}

  .tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }}
  .q-num  {{ color: var(--muted); margin-right: 8px; }}
  .q-text {{ color: var(--text); }}
  .q-count{{
    background: rgba(0,201,167,0.15);
    color: var(--teal);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    white-space: nowrap;
  }}

  .footer {{
    margin-top: 60px;
    padding: 20px 48px;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 10px;
    display: flex;
    justify-content: space-between;
  }}

  .hal-explanation {{
    background: rgba(239,35,60,0.06);
    border: 1px solid rgba(239,35,60,0.2);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
    color: var(--text);
    line-height: 1.7;
  }}
  .hal-explanation ul {{ padding-left: 20px; margin-top: 8px; }}
  .hal-explanation li {{ margin-bottom: 4px; font-size: 12px; color: var(--muted); }}
  .hal-explanation li strong {{ color: var(--text); }}
  .hal-summary-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }}
  .hal-card {{
    border-radius: 10px;
    padding: 18px 16px;
    text-align: center;
    border: 1px solid var(--border);
  }}
  .hal-safe   {{ background: rgba(0,201,167,0.08); border-color: rgba(0,201,167,0.3); }}
  .hal-risk   {{ background: rgba(255,214,10,0.08); border-color: rgba(255,214,10,0.3); }}
  .hal-warn   {{ background: rgba(247,127,0,0.08); border-color: rgba(247,127,0,0.3); }}
  .hal-danger {{ background: rgba(239,35,60,0.08); border-color: rgba(239,35,60,0.3); }}
  .hal-num {{
    font-family: 'Syne', sans-serif;
    font-size: 32px;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 6px;
  }}
  .hal-safe   .hal-num {{ color: var(--teal); }}
  .hal-risk   .hal-num {{ color: var(--yellow); }}
  .hal-warn   .hal-num {{ color: var(--orange); }}
  .hal-danger .hal-num {{ color: var(--red); }}
  .hal-label {{ color: var(--muted); font-size: 11px; line-height: 1.4; }}
  .hal-label small {{ font-size: 10px; opacity: 0.7; }}

  @media (max-width: 900px) {{
    .header {{ padding: 24px; flex-direction: column; }}
    .container {{ padding: 0 24px 40px; }}
    .charts-grid.cols-2, .charts-grid.cols-3 {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    h1 {{ font-size: 26px; }}
    .footer {{ padding: 20px 24px; flex-direction: column; gap: 6px; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="badge">Competition Analytics</div>
    <h1>NovaCortex v13<br>Intelligence Dashboard</h1>
    <div class="header-meta">
      <span><span class="status-dot"></span> Live System</span>
      <span>📂 {db_path}</span>
      <span>🕐 {now_str}</span>
    </div>
  </div>
</div>

<div class="container">

<div class="kpi-grid">
  {kpi("📨", "Total Queries",      f"{total:,}",                  f"{pct(total,total)} processed",     C["teal"])}
  {kpi("🎯", "Avg Confidence",     f"{avg_conf:.1f}%",            f"{high_conf} high / {low_conf} low",C["blue"])}
  {kpi("⚡", "Avg Response Time",  fmt_ms(avg_rt),                f"median {fmt_ms(median_rt)}",       C["orange"])}
  {kpi("🚀", "Fast Responses",     f"{fast_pct:.1f}%",            "under 2 seconds",                   C["green"])}
  {kpi("🛡️", "Guardrail Rate",    f"{pct(guardrail_total,total)}",f"{guardrail_total} blocked",        C["red"])}
  {kpi("✅", "Deterministic",      f"{pct(deterministic,total)}", f"{deterministic} from facts/cache", C["teal"])}
  {kpi("💾", "Cache Hit Rate",     f"{cache_hit_rate:.1f}%",      f"{total_cache_entries} entries",    C["yellow"])}
  {kpi("❌", "Error Rate",         f"{error_rate:.1f}%",          f"{sc['error']} errors",             C["red"] if error_rate>5 else C["green"])}
  {kpi("👥", "Total Users",        f"{total_users}",              f"{active_7d} active (7d)",          C["purple"])}
  {kpi("🌐", "Arabic Queries",     pct(lang_counts.get('arabic',0),total), f"{lang_counts.get('arabic',0)} questions", C["blue"])}
  {kpi("📚", "Avg Docs (RAG)",     f"{avg_docs:.1f}",             "docs per RAG query",                C["muted"])}
  {kpi("🧠", "Hallucination Risk",  f"{hal_risk_score:.1f}/50",      hal_level[0],                        hal_level[1])}
  {kpi("⚠️", "Low Conf Responses", f"{low_conf_responses}",         f"{pct(low_conf_responses,total)} of total", C["orange"])}
  {kpi("🔥", "High Risk (LLM FB)", f"{high_risk_responses}",        f"{pct(high_risk_responses,total)} risky",   C["red"])}
  {kpi("✅", "Safe Response Rate", f"{safe_rate:.1f}%",              f"{safe_count} zero-risk answers",           C["teal"])}
  {kpi("🧠", "Conversations",      f"{total_msgs}",               f"avg {avg_msgs_user:.1f}/user", C["purple"])}
</div>

{section("🔀 Query Pipeline Analysis", charts["waterfall"], charts["sources"])}

{section("🛡️ Safety & Guardrail System", charts["guard"],
  table_html(["Guardrail Type","Count","Rate"], guardrail_rows_html, "Full Guardrail Breakdown")
)}

{section("📈 Performance Trends", charts["trend"], charts["time"], cols=1)}
{section("⚡ Response Speed", charts["rt"], charts["heat"])}

{section("🎯 Confidence Analysis", charts["conf"], charts["scatter"])}

{section("🌐 Language & User Insights", charts["lang"], charts["level"])}

<section>
  <h2 class="section-title">🔥 Top 10 Most Asked Questions</h2>
  <div class="charts-grid cols-1">
    {table_html(["#","Question","Times Asked"], top_q_rows_html)}
  </div>
</section>

<section>
  <h2 class="section-title">📊 Full Source Distribution</h2>
  <div class="charts-grid cols-2">
    {table_html(["Source","Count","Rate"], source_rows_html, "All Response Sources")}
    {charts["cache"]}
  </div>
</section>

</div>

<section>
  <h2 class="section-title">🧠 Hallucination Risk Analysis</h2>

  <div class="hal-explanation">
    <p><strong>ما هي الهلوسة؟</strong> لما البوت يجاوب بثقة وهو في الواقع غلط، ناقص، أو مش مبني على مصدر موثوق.</p>
    <p>نقيسها بـ <strong>4 مستويات</strong>: الـ Risk Score الكلي، توزيع الـ Confidence، خطر كل مصدر، والاتجاه مع الوقت.</p>
  </div>

  <div class="hal-summary-grid">
    <div class="hal-card hal-safe">
      <div class="hal-num">{safe_rate:.1f}%</div>
      <div class="hal-label">✅ Zero-Risk Responses<br><small>verified_facts + cache + guardrails</small></div>
    </div>
    <div class="hal-card hal-risk">
      <div class="hal-num">{hal_risk_score:.1f}<span style="font-size:14px">/50</span></div>
      <div class="hal-label">{hal_level[0]}<br><small>Overall Hallucination Risk Score</small></div>
    </div>
    <div class="hal-card hal-warn">
      <div class="hal-num">{low_conf_responses}</div>
      <div class="hal-label">⚠️ Low Confidence Answers<br><small>confidence &lt; 70% — potentially incomplete</small></div>
    </div>
    <div class="hal-card hal-danger">
      <div class="hal-num">{high_risk_responses}</div>
      <div class="hal-label">🔥 Highest Risk Responses<br><small>llm_fallback — no grounding source</small></div>
    </div>
  </div>

  <div class="charts-grid cols-2">
    <div class="chart-card">{charts["gauge"]}</div>
    <div class="chart-card">{charts["hal_buckets"]}</div>
    <div class="chart-card">{charts["hal_src"]}</div>
    <div class="chart-card">{charts["hal_time"]}</div>
  </div>

  <div class="hal-explanation" style="margin-top:16px">
    <p><strong>كيف نقرأ النتائج:</strong></p>
    <ul>
      <li><strong>Risk Score &lt; 5:</strong> ممتاز — معظم الإجابات من مصادر موثوقة</li>
      <li><strong>Risk Score 5-15:</strong> جيد — نسبة صغيرة من RAG/Web</li>
      <li><strong>Risk Score 15-30:</strong> تحذير — زيادة في LLM Fallback أو Web</li>
      <li><strong>Risk Score &gt; 30:</strong> مشكلة — النظام يعتمد كثيراً على LLM بدون مصادر</li>
      <li><strong>Confidence &lt; 70%:</strong> الإجابة ممكن تكون غلط أو ناقصة — راجعها يدوياً</li>
    </ul>
  </div>
</section>

<div class="footer">
  <span>NovaCortex v13 · Yarmouk University Chatbot · Competition Dashboard</span>
  <span>Generated {now_str} · DB: {db_path} · {total:,} queries analyzed</span>
</div>

</body>
</html>"""

    out = ROOT / "dashboard_output"
    out.mkdir(exist_ok=True)
    output_file = out / "index.html"
    output_file.write_text(html, encoding="utf-8")

    # ── export markdown report ──────────────────────
    report = f"""# NovaCortex v13 — Competition Report
Generated: {now_str} | Database: {db_path}

## Core KPIs
| Metric | Value |
|--------|-------|
| Total Queries | {total:,} |
| Avg Confidence | {avg_conf:.2f}% |
| Avg Response Time | {fmt_ms(avg_rt)} |
| Fast Responses (<2s) | {fast_pct:.1f}% |
| Error Rate | {error_rate:.1f}% |
| Cache Hit Rate | {cache_hit_rate:.1f}% |
| Total Users | {total_users} |
| Active (7d) | {active_7d} |

## Guardrail System
| Type | Count | Rate |
|------|-------|------|
| Out of Scope | {sc['out_of_scope']} | {pct(sc['out_of_scope'],total)} |
| Injection Blocked | {sc['injection_blocked']} | {pct(sc['injection_blocked'],total)} |
| False Premise Corrected | {sc['false_premise_corrected']} | {pct(sc['false_premise_corrected'],total)} |
| Comparison Rejected | {sc['comparison_rejected']} | {pct(sc['comparison_rejected'],total)} |
| **TOTAL BLOCKED** | **{guardrail_total}** | **{pct(guardrail_total,total)}** |

## Pipeline Distribution
| Path | Count | Rate |
|------|-------|------|
| Verified Facts + Cache | {deterministic} | {pct(deterministic,total)} |
| RAG | {rag_count} | {pct(rag_count,total)} |
| Web Search | {web_count} | {pct(web_count,total)} |
| LLM Fallback | {llm_fb_count} | {pct(llm_fb_count,total)} |

## Language Analysis
| Language | Count | Rate |
|----------|-------|------|
| Arabic | {lang_counts.get('arabic',0)} | {pct(lang_counts.get('arabic',0),total)} |
| English | {lang_counts.get('english',0)} | {pct(lang_counts.get('english',0),total)} |

## Top 10 Questions
{chr(10).join(f"{i+1}. {q} ({c}×)" for i,(q,c) in enumerate(top_qs))}

## Memory & Cache
- Conversation Messages: {total_msgs}
- Avg per User: {avg_msgs_user:.1f}
- Summary Rate: {summary_rate:.1f}%
- Cache Entries: {total_cache_entries}
- Avg Cache Hits: {avg_cache_hits:.1f}
"""
    (out / "competition_report.md").write_text(report, encoding="utf-8")

    print(f"\n✅ Dashboard ready!")
    print(f"🌐 Open:   dashboard_output/index.html")
    print(f"📄 Report: dashboard_output/competition_report.md")
    print(f"\n📊 Quick Stats:")
    print(f"   Queries:    {total:,}")
    print(f"   Confidence: {avg_conf:.1f}%")
    print(f"   Guardrails: {pct(guardrail_total,total)} ({guardrail_total} blocked)")
    print(f"   Speed:      {fmt_ms(avg_rt)} avg ({fast_pct:.1f}% under 2s)")

if __name__ == "__main__":
    create_dashboard()