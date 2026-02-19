import pandas as pd
import plotly.express as px
import streamlit as st
import subprocess
import sys
from datetime import datetime

st.set_page_config(page_title="Engineering Impact Dashboard", page_icon="📊", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"]  {
  font-family: 'Space Grotesk', sans-serif;
}

/* Layout */
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

/* Headline */
.title {
  font-size: 2.2rem;
  font-weight: 700;
  margin-bottom: 0.15rem;
}
.subtitle {
  color: #6b6f76;
  font-size: 0.95rem;
  margin-bottom: 1.2rem;
}

/* Cards */
.kpi {
  background: linear-gradient(145deg, #e9f3ff, #f7fbff) !important;
  border: 1px solid #cfe2ff !important;
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 6px 20px rgba(20, 20, 20, 0.05);
}
.kpi-label {
  color: #3b4a5a !important;
  font-size: 0.85rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.kpi-value {
  color: #0f172a !important;
  font-size: 1.6rem;
  font-weight: 700;
  margin-top: 0.25rem;
}

/* Section headers */
.section-title {
  margin-top: 1.2rem;
  margin-bottom: 0.4rem;
  font-size: 1.2rem;
  font-weight: 600;
}

/* Button */
div.stButton > button {
  background-color: #d43f3a;
  color: white;
  border: 1px solid #c12f2a;
  border-radius: 10px;
  padding: 0.6rem 1.1rem;
  font-weight: 600;
}
div.stButton > button:hover {
  background-color: #b9332f;
  border-color: #b9332f;
}
</style>
""",
    unsafe_allow_html=True,
)

scores_path = "data/engineer_scores.csv"

st.markdown('<div class="title">Engineering Impact — PostHog</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Last 90 days • Impact = shipping changes + unblocking others (measured via PR and issue activity)</div>', unsafe_allow_html=True)

days_back = st.number_input("Days Back", min_value=7, max_value=180, value=90, step=7)
run_btn = st.button("Get Results", use_container_width=True)

last_run = st.session_state.get("last_run")
if last_run:
    st.caption(f"Last run: {last_run}")

if run_btn:
    with st.status("Running data pipeline...", expanded=True) as status:
        try:
            status.write("Fetching data from GitHub...")
            subprocess.run(
                [sys.executable, "fetch_data.py", "--days-back", str(days_back)],
                check=True,
            )
            status.write("Computing metrics...")
            subprocess.run([sys.executable, "compute_metrics.py"], check=True)
            st.session_state["last_run"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            status.update(label="Pipeline complete", state="complete")
        except subprocess.CalledProcessError as exc:
            status.update(label="Pipeline failed", state="error")
            st.error(f"Pipeline failed. Check logs in terminal. Exit code: {exc.returncode}")

try:
    df = pd.read_csv(scores_path)
except FileNotFoundError:
    st.error("Missing `data/engineer_scores.csv`. Run the pipeline from the main page.")
    st.stop()

if df.empty:
    st.warning("No data available. Check your fetch script and API access.")
    st.stop()

top5 = df.sort_values("impact_score", ascending=False).head(5)

st.markdown("**Impact Definition**")
st.markdown(
    """
Impact here means **delivering meaningful changes to the codebase while removing friction for others**.
We capture this with a blend of PR throughput and issue lifecycle activity in the last 90 days.
    """
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.markdown('<div class="kpi"><div class="kpi-label">Top Engineer</div><div class="kpi-value">{}</div></div>'.format(top5.iloc[0]["engineer"]), unsafe_allow_html=True)
with kpi2:
    st.markdown('<div class="kpi"><div class="kpi-label">Top Score</div><div class="kpi-value">{:.2f}</div></div>'.format(top5.iloc[0]["impact_score"]), unsafe_allow_html=True)
with kpi3:
    st.markdown('<div class="kpi"><div class="kpi-label">PRs Merged (Top 5)</div><div class="kpi-value">{}</div></div>'.format(int(top5["prs_merged"].sum())), unsafe_allow_html=True)
with kpi4:
    st.markdown('<div class="kpi"><div class="kpi-label">Issues Closed (Top 5)</div><div class="kpi-value">{}</div></div>'.format(int(top5.get("issues_closed", pd.Series([0])).sum())), unsafe_allow_html=True)

st.markdown('<div class="section-title">Leaderboard</div>', unsafe_allow_html=True)
display_cols = [
    "rank",
    "engineer",
    "impact_score",
    "prs_merged",
    "prs_closed",
    "issues_closed",
    "prs_opened",
    "pr_comments",
    "issues_opened",
]
display_cols = [c for c in display_cols if c in top5.columns]
st.dataframe(top5[display_cols], use_container_width=True, height=260)

st.markdown('<div class="section-title">Why These Rankings</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    fig = px.bar(top5, x="engineer", y="prs_merged", title="PRs Merged", color="engineer")
    fig.update_layout(showlegend=False, height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    if "prs_closed" in top5.columns:
        fig = px.bar(top5, x="engineer", y="prs_closed", title="PRs Closed", color="engineer")
        fig.update_layout(showlegend=False, height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No PR closed data available.")

with col3:
    if "issues_closed" in top5.columns:
        fig = px.bar(top5, x="engineer", y="issues_closed", title="Issues Closed (by Opener)", color="engineer")
        fig.update_layout(showlegend=False, height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No issues data available.")

with st.expander("Scoring Model"):
    st.markdown(
        """
Impact score is a weighted combination of normalized signals:

- PRs merged (45%) — strongest proxy for shipping value
- PRs closed (15%) — finishing work, even if not merged
- Issues closed (by opener, due to API limits) (15%) — resolving tracked work
- PRs opened (10%) — initiating changes
- Issues opened (10%) — surfacing work to be done
- PR conversation comments (5%) — collaboration around delivery
        """
    )

with st.expander("FAQs"):
    st.markdown(
        """
**Why this definition of impact?**  
We define impact as a balance between **delivering change** (PRs merged/closed) and **unblocking work** (issue activity).
It’s simple, explainable, and aligns with what leaders care about: shipping and throughput.

**Why is this useful for the target audience?**  
Busy engineering leaders need a fast, defensible snapshot of who is shipping and unblocking work without reading every PR.
This view surfaces outcomes and coordination signals at a glance, which is the right level of abstraction for leadership.

**Why not use lines of code or commit count?**  
Those measures are noisy and can over‑reward churn. We prefer signals tied to completion and coordination.

**Why is “issues closed” attributed to the opener?**  
GitHub’s Search API doesn’t expose `closed_by`. To keep API calls low, we attribute closed issues to the opener as a proxy.
If you want true closers, we can add per‑issue detail calls at the cost of more API usage.

**Why normalize metrics?**  
Different signals are on different scales. Normalization prevents any single metric from dominating purely by magnitude.
        """
    )
