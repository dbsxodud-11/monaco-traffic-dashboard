"""
Monaco Traffic Network Dashboard
================================
Run with:
    conda activate AgentSUMO
    streamlit run dashboard.py

Reads results/Monaco/dashboard/dashboard_data.pkl produced by
collect_dashboard_data.py.

Tab 1  — Network Explorer : pick a network, see an animated congestion map
                            (red = jammed, green = free-flowing) on the left and
                            traffic metrics on the right. Press ▶ to play.
Tab 2  — Network Comparison: pick a degraded network, see which roads were
                            removed/added vs. the base network and how the
                            resulting traffic flow changed.
"""
import os
import pickle

import numpy as np
import streamlit as st
import plotly.graph_objects as go

DATA_PATH = "results/Monaco/dashboard/dashboard_data.pkl"

# ---- congestion color buckets (speed / speed-limit ratio, 1=free, 0=jam) ----
#  lower-bound, color, label
CONG_BUCKETS = [
    (0.70, "#2ecc71", "원활 (Free flow)"),
    (0.45, "#f4d03f", "다소 정체 (Slow)"),
    (0.20, "#e67e22", "정체 (Heavy)"),
    (0.00, "#e74c3c", "심각 정체 (Jam)"),
]


def cong_bucket(ratio):
    for i, (lo, _, _) in enumerate(CONG_BUCKETS):
        if ratio >= lo:
            return i
    return len(CONG_BUCKETS) - 1


@st.cache_data
def load_data(mtime):  # mtime keys the cache so it reloads when the file changes
    with open(DATA_PATH, "rb") as f:
        return pickle.load(f)


# --------------------------------------------------------------------------- #
#  Figure builders
# --------------------------------------------------------------------------- #
def _background_trace(edges, color="rgba(150,150,150,0.35)", width=1.8):
    bx, by = [], []
    for g in edges.values():
        for (x, y) in g["shape"]:
            bx.append(x)
            by.append(y)
        bx.append(None)
        by.append(None)
    return go.Scattergl(x=bx, y=by, mode="lines",
                        line=dict(color=color, width=width),
                        hoverinfo="skip", showlegend=False, name="도로망")


def _congestion_frame_traces(edges, frame_ratios):
    """Return [bucket0..3 line traces, hover-marker trace] for one time bin."""
    bucket_xy = [([], []) for _ in CONG_BUCKETS]
    mx, my, mc, mt = [], [], [], []
    for eid, g in edges.items():
        r = frame_ratios.get(eid)
        if r is None:
            continue
        bi = cong_bucket(r)
        xs_, ys_ = bucket_xy[bi]
        for (x, y) in g["shape"]:
            xs_.append(x)
            ys_.append(y)
        xs_.append(None)
        ys_.append(None)
        mid = g["shape"][len(g["shape"]) // 2]
        mx.append(mid[0]); my.append(mid[1]); mc.append(r)
        mt.append(f"{eid}<br>속도비 {r:.2f}")

    traces = []
    for bi, (_, color, label) in enumerate(CONG_BUCKETS):
        xs_, ys_ = bucket_xy[bi]
        traces.append(go.Scattergl(x=xs_, y=ys_, mode="lines",
                                  line=dict(color=color, width=5.0),
                                  hoverinfo="skip", name=label))
    traces.append(go.Scattergl(x=mx, y=my, mode="markers",
                              marker=dict(size=6, color=mc, colorscale="RdYlGn",
                                          cmin=0, cmax=1, showscale=False,
                                          line=dict(width=0)),
                              text=mt, hoverinfo="text",
                              showlegend=False, name="edge"))
    return traces


def _map_layout(bounds, title, height=680):
    xmin, ymin, xmax, ymax = bounds
    pad = 0.03 * max(xmax - xmin, ymax - ymin)
    return dict(
        title=dict(text=title, font=dict(size=18, color="#f0f3f7")),
        height=height,
        margin=dict(l=12, r=12, t=54, b=12),
        plot_bgcolor="#0b0e14",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdd3dc", family="sans-serif"),
        xaxis=dict(visible=False, range=[xmin - pad, xmax + pad]),
        yaxis=dict(visible=False, range=[ymin - pad, ymax + pad],
                   scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=12)),
        hoverlabel=dict(bgcolor="#161b26", bordercolor="#4dd4ac",
                        font=dict(color="#e6e6e6")),
    )


def build_congestion_figure(net, bounds=None):
    edges = net["edges"]
    ts = net["timeseries"]
    begins = net["begins"]
    bounds = bounds or net["bounds"]

    if not ts:
        fig = go.Figure(data=[_background_trace(edges)])
        fig.update_layout(**_map_layout(bounds, "혼잡도 (데이터 없음)"))
        return fig

    n_anim = len(CONG_BUCKETS) + 1  # bucket lines + marker layer
    init = [_background_trace(edges)] + _congestion_frame_traces(edges, ts[0])

    frames = []
    for i, frame_ratios in enumerate(ts):
        frames.append(go.Frame(
            data=_congestion_frame_traces(edges, frame_ratios),
            traces=list(range(1, 1 + n_anim)),
            name=f"{int(begins[i])}s",
        ))

    fig = go.Figure(data=init, frames=frames)
    fig.update_layout(**_map_layout(bounds, "🗺️ 교통 혼잡도 (▶ 재생)"))

    play_args = dict(frame=dict(duration=500, redraw=True),
                     fromcurrent=True, transition=dict(duration=0))
    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="left",
            x=0.0, y=-0.03, xanchor="left", yanchor="top",
            pad=dict(t=6, r=6),
            bgcolor="#1c2230", bordercolor="#4dd4ac", borderwidth=1.2,
            font=dict(color="#e6e6e6", size=13),
            buttons=[
                dict(label="▶  재생", method="animate", args=[None, play_args]),
                dict(label="⏸  정지", method="animate",
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                        mode="immediate")]),
            ],
        )],
        sliders=[dict(
            active=0, x=0.14, len=0.86, y=-0.03, xanchor="left", yanchor="top",
            bgcolor="#2a3242", bordercolor="#2a3242",
            activebgcolor="#4dd4ac", tickcolor="#4a5568",
            font=dict(color="#a8b1bf", size=11),
            currentvalue=dict(prefix="시각: ", font=dict(size=13, color="#4dd4ac")),
            steps=[dict(method="animate", label=f"{int(b)}s",
                        args=[[f"{int(b)}s"],
                              dict(mode="immediate",
                                   frame=dict(duration=0, redraw=True),
                                   transition=dict(duration=0))])
                   for b in begins],
        )],
    )
    return fig


def build_removed_added_figure(base, gen, bounds=None):
    base_edges = base["edges"]
    gen_edges = gen["edges"]
    traces = [_background_trace(base_edges, color="rgba(120,120,120,0.30)", width=1.6)]

    def seg(edge_ids, geom_src, color, label, width):
        xs_, ys_ = [], []
        for eid in edge_ids:
            g = geom_src.get(eid)
            if g is None:
                continue
            for (x, y) in g["shape"]:
                xs_.append(x); ys_.append(y)
            xs_.append(None); ys_.append(None)
        return go.Scattergl(x=xs_, y=ys_, mode="lines",
                           line=dict(color=color, width=width),
                           hoverinfo="skip", name=label)

    traces.append(seg(gen["removed_edges"], base_edges, "#e74c3c",
                      f"제거된 도로 ({gen['num_removed']})", 5.0))
    if gen["num_added"] > 0:
        traces.append(seg(gen["added_edges"], gen_edges, "#3498db",
                          f"추가된 도로 ({gen['num_added']})", 5.0))

    fig = go.Figure(data=traces)
    fig.update_layout(**_map_layout(bounds or base["bounds"],
                                    "🔧 기존(default) 대비 도로 변화"))
    return fig


def build_flow_change_figure(base, gen, bounds=None):
    """Diverging map of per-edge congestion change vs. base (on shared edges),
    with removed roads overlaid."""
    gen_edges = gen["edges"]
    base_edges = base["edges"]
    flow_delta = gen["flow_delta"]

    # only improvements are highlighted; everything else stays neutral gray
    pos_x, pos_y = [], []     # improved (green)
    other_x, other_y = [], []  # similar or worse (neutral)
    mx, my, mc, mt = [], [], [], []
    for eid, d in flow_delta.items():
        if np.isnan(d):
            continue
        g = gen_edges.get(eid)
        if g is None:
            continue
        tgt = (pos_x, pos_y) if d >= 0.1 else (other_x, other_y)
        for (x, y) in g["shape"]:
            tgt[0].append(x); tgt[1].append(y)
        tgt[0].append(None); tgt[1].append(None)
        mid = g["shape"][len(g["shape"]) // 2]
        mx.append(mid[0]); my.append(mid[1]); mc.append(max(d, 0.0))
        mt.append(f"{eid}<br>혼잡 변화 {d:+.2f}")

    traces = [
        go.Scattergl(x=other_x, y=other_y, mode="lines",
                    line=dict(color="rgba(150,150,150,0.5)", width=2.4),
                    hoverinfo="skip", name="기타"),
        go.Scattergl(x=pos_x, y=pos_y, mode="lines",
                    line=dict(color="#2ecc71", width=5.0),
                    hoverinfo="skip", name="흐름 개선 (빨라짐)"),
    ]
    # removed roads as dashed reference
    rx, ry = [], []
    for eid in gen["removed_edges"]:
        g = base_edges.get(eid)
        if g is None:
            continue
        for (x, y) in g["shape"]:
            rx.append(x); ry.append(y)
        rx.append(None); ry.append(None)
    traces.append(go.Scattergl(x=rx, y=ry, mode="lines",
                              line=dict(color="rgba(255,255,255,0.6)", width=1.8,
                                        dash="dot"),
                              hoverinfo="skip", name="제거된 도로"))
    traces.append(go.Scattergl(x=mx, y=my, mode="markers",
                              marker=dict(size=5, color=mc,
                                          colorscale=[[0, "rgba(120,120,120,0.5)"],
                                                      [1, "#2ecc71"]],
                                          cmin=0.0, cmax=0.4, showscale=False),
                              text=mt, hoverinfo="text", showlegend=False))

    fig = go.Figure(data=traces)
    fig.update_layout(**_map_layout(bounds or base["bounds"],
                                    "🌊 교통 흐름 변화 (기존 대비)"))
    return fig


# --------------------------------------------------------------------------- #
#  Metric helpers
# --------------------------------------------------------------------------- #
def network_congestion_summary(net):
    ratios = list(net["avg_ratio"].values())
    if not ratios:
        return float("nan"), float("nan")
    arr = np.array(ratios)
    overall = float(arr.mean())
    jam_pct = float((arr < 0.45).mean() * 100)
    return overall, jam_pct


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Monaco 교통 네트워크 대시보드",
                   layout="wide", page_icon="🚦")

st.markdown(
    """
    <style>
    /* ---- app background: deep dark gradient ---- */
    .stApp {
        background: radial-gradient(1200px 600px at 20% -10%, #16203a 0%, #0b0e14 55%) ,
                    #0b0e14;
    }
    .block-container { padding-top: 2.2rem; padding-bottom: 2rem; }

    /* ---- title ---- */
    h1 {
        background: linear-gradient(90deg, #4dd4ac 0%, #5bc0ff 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800; letter-spacing: -0.5px;
    }

    /* ---- tabs ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #161b26; border-radius: 10px 10px 0 0;
        padding: 10px 22px; color: #9aa4b2; font-weight: 600;
        border: 1px solid #232a38; border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background: #1c2740; color: #4dd4ac;
        border-color: #2f6f5e;
    }

    /* ---- metric cards ---- */
    [data-testid="stMetric"] {
        background: linear-gradient(160deg, #171d2b 0%, #131722 100%);
        border: 1px solid #242c3b; border-radius: 14px;
        padding: 14px 16px 10px 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    }
    [data-testid="stMetricLabel"] p { color: #8a93a3; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #f0f3f7; font-weight: 700; }

    /* ---- selectbox ---- */
    div[data-baseweb="select"] > div {
        background: #161b26; border: 1px solid #2a3242;
        border-radius: 10px;
    }

    /* ---- captions / dividers ---- */
    [data-testid="stCaptionContainer"] { color: #8a93a3; }
    hr { border-color: #242c3b; }
    </style>
    """,
    unsafe_allow_html=True,
)

if not os.path.exists(DATA_PATH):
    st.error(f"데이터 파일이 없습니다: {DATA_PATH}\n\n"
             "먼저 `python collect_dashboard_data.py` 를 실행하세요.")
    st.stop()

data = load_data(os.path.getmtime(DATA_PATH))
base = data["base"]
networks = data["networks"]
net_names = list(networks.keys())
all_names = ["base"] + net_names
MAP_BOUNDS = data.get("map_bounds")


def net_label(name):
    return "기존 (default)" if name == "base" else name


st.title("🚦 Monaco 교통 네트워크 대시보드")

tab1, tab2 = st.tabs(["🗺️ 네트워크 탐색", "🔀 네트워크 비교"])

# ----------------------------- Tab 1 --------------------------------------- #
with tab1:
    sel = st.selectbox("네트워크 선택", all_names, index=0, key="explore_sel",
                       format_func=net_label)
    net = base if sel == "base" else networks[sel]

    left, right = st.columns([2, 1.15], gap="large")

    with left:
        st.plotly_chart(build_congestion_figure(net, bounds=MAP_BOUNDS),
                        width="stretch", config={"displayModeBar": False})

    with right:
        st.subheader("📊 지표")
        m = net["metrics"]
        overall_ratio, jam_pct = network_congestion_summary(net)

        r1 = st.columns(2)
        r2 = st.columns(2)
        if sel == "base":
            r1[0].metric("도착 차량", f"{m['num_arrived']:,} 대")
            r1[1].metric("평균 대기시간", f"{m['avg_waiting_time']:.1f} s")
            r2[0].metric("평균 주행시간", f"{m['avg_travel_time']:.1f} s")
            r2[1].metric("평균 지연시간", f"{m['avg_time_loss']:.1f} s")
        else:
            bm = base["metrics"]
            r1[0].metric("도착 차량", f"{m['num_arrived']:,} 대",
                         delta=f"{m['num_arrived'] - bm['num_arrived']:+,}")
            r1[1].metric("평균 대기시간", f"{m['avg_waiting_time']:.1f} s",
                         delta=f"{m['avg_waiting_time'] - bm['avg_waiting_time']:+.1f} s",
                         delta_color="inverse")
            r2[0].metric("평균 주행시간", f"{m['avg_travel_time']:.1f} s",
                         delta=f"{m['avg_travel_time'] - bm['avg_travel_time']:+.1f} s",
                         delta_color="inverse")
            r2[1].metric("평균 지연시간", f"{m['avg_time_loss']:.1f} s",
                         delta=f"{m['avg_time_loss'] - bm['avg_time_loss']:+.1f} s",
                         delta_color="inverse")

        st.divider()
        s1 = st.columns(2)
        s1[0].metric("전체 평균 속도비", f"{overall_ratio:.2f}",
                     help="1에 가까울수록 원활 (제한속도 대비 평균 주행속도)")
        s1[1].metric("정체 도로 비율", f"{jam_pct:.0f} %",
                     help="속도비 0.45 미만 도로 비중")
        s2 = st.columns(2)
        s2[0].metric("마지막 도착 시각", f"{m['last_arrival']:.0f} s")
        if sel != "base":
            s2[1].metric("제거된 도로 수", f"{net['num_removed']} 개")

        st.caption("🟢 원활 · 🟡 다소 정체 · 🟠 정체 · 🔴 심각 정체")

# ----------------------------- Tab 2 --------------------------------------- #
with tab2:
    sel2 = st.selectbox("비교할 네트워크 선택", net_names, index=0, key="compare_sel")
    gen = networks[sel2]

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(build_removed_added_figure(base, gen, bounds=MAP_BOUNDS),
                        width="stretch", config={"displayModeBar": False})
        st.caption(f"🔴 제거된 도로 {gen['num_removed']}개 · "
                   f"🔵 추가된 도로 {gen['num_added']}개 (기존 default 대비)")
    with c2:
        st.plotly_chart(build_flow_change_figure(base, gen, bounds=MAP_BOUNDS),
                        width="stretch", config={"displayModeBar": False})
        st.caption("🟢 기존보다 흐름이 빨라진 도로 · ⚪ 점선 = 제거된 도로")

    st.divider()
    st.subheader(f"📋 {sel2} vs 기존 네트워크")
    bm = base["metrics"]
    m = gen["metrics"]
    delta = gen["flow_delta"]
    deltas = np.array([d for d in delta.values() if not np.isnan(d)])
    better = int((deltas >= 0.1).sum())

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("제거된 도로", f"{gen['num_removed']} 개")
    k2.metric("추가된 도로", f"{gen['num_added']} 개")
    k3.metric("흐름 개선 도로", f"{better} 개")
    k4.metric("평균 대기시간", f"{m['avg_waiting_time']:.1f} s",
              delta=f"{m['avg_waiting_time'] - bm['avg_waiting_time']:+.1f} s",
              delta_color="inverse")
    k5.metric("도착 차량", f"{m['num_arrived']:,} 대",
              delta=f"{m['num_arrived'] - bm['num_arrived']:+,}")
