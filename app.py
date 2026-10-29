from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# Page configuration and visual system
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="CareerLens | Youth Career Insights",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
      :root { --ink:#182230; --muted:#68758a; --purple:#5b4bdb; --violet:#7c3aed; --teal:#0f9f9a; --line:#e5e9f2; }
      html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
      .stApp { background: #f6f7fc; color:var(--ink); }
      [data-testid="stHeader"] { background:rgba(246,247,252,.92); }
      [data-testid="stSidebar"] { background:#171a2c; border-right:1px solid #292d44; }
      [data-testid="stSidebar"] * { color:#f6f7ff; }
      [data-testid="stSidebar"] [data-testid="stFileUploader"] { background:#22263b; border:1px solid #373c59; border-radius:12px; padding:10px; }
      .block-container { max-width:1500px; padding-top:1.5rem; padding-bottom:3rem; }
      h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.025em; color:#192238; }
      h1 { font-weight:800; }
      .hero { background:linear-gradient(118deg,#25245f 0%,#5141b8 54%,#7c3aed 100%); color:white; padding:30px 34px; border-radius:22px; margin:0 0 22px 0; box-shadow:0 14px 35px rgba(55,45,130,.16); }
      .hero h1 { color:white !important; font-size:clamp(1.65rem,3vw,2.45rem); margin:0 0 8px 0; line-height:1.2; }
      .hero p { color:#eeedff !important; margin:6px 0 0 0; font-size:1rem; max-width:900px; }
      .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-weight:700; font-size:.73rem; color:#c8c3ff; margin-bottom:10px; }
      .section-intro { color:#667085; margin-top:-4px; margin-bottom:18px; font-size:.98rem; }
      .mini-label { color:#667085; font-size:.8rem; font-weight:700; letter-spacing:.045em; text-transform:uppercase; }
      .insight-card { background:white; border:1px solid var(--line); border-radius:16px; padding:18px 20px; box-shadow:0 4px 16px rgba(26,36,70,.035); height:100%; }
      .insight-card h4 { margin:0 0 7px 0; color:#202944; font-size:1rem; }
      .insight-card p { margin:0; color:#68758a; line-height:1.55; font-size:.92rem; }
      .pill { display:inline-block; border-radius:99px; background:#eeecff; color:#4b3ec7; font-size:.78rem; font-weight:700; padding:5px 10px; margin-bottom:9px; }
      .notice { border-left:4px solid #7c72e8; background:#efefff; border-radius:8px; padding:12px 15px; color:#38356e; margin:12px 0 18px 0; }
      .stMetric { background:white; border:1px solid var(--line); padding:16px 18px; border-radius:16px; box-shadow:0 4px 16px rgba(26,36,70,.035); }
      [data-testid="stMetricLabel"] { color:#68758a; font-weight:600; }
      [data-testid="stMetricValue"] { color:#22234f; font-family:'Manrope',sans-serif; font-weight:800; }
      div[data-testid="stPlotlyChart"] { background:white; border:1px solid var(--line); border-radius:16px; padding:8px 8px 0 8px; box-shadow:0 4px 16px rgba(26,36,70,.025); }
      div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
      .footer-note { color:#7b8496; font-size:.82rem; border-top:1px solid #e2e6f0; padding-top:14px; margin-top:26px; }
      .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:700; border:1px solid #d9d8f7; }
      .stButton > button[kind="primary"] { background:#5546d8; border-color:#5546d8; }
      @media (max-width: 700px) { .hero {padding:22px;} .block-container {padding-left:1rem;padding-right:1rem;} }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "survey_responses.csv"

SKILL_PREFIX = "Please rate your current level in the following career-related skills"
IDENTIFYING_TERMS = ("name", "college/institution", "institution name", "email", "phone", "contact")


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in out.columns]
    # Duplicate headers can occur in manually edited CSV files; make them unique.
    seen: dict[str, int] = {}
    new_cols = []
    for col in out.columns:
        seen[col] = seen.get(col, 0) + 1
        new_cols.append(col if seen[col] == 1 else f"{col} ({seen[col]})")
    out.columns = new_cols
    return out


def find_col(df: pd.DataFrame, *needles: str) -> Optional[str]:
    for col in df.columns:
        low = col.casefold()
        if all(n.casefold() in low for n in needles):
            return col
    return None


def text_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    if not col or col not in df.columns:
        return pd.Series(dtype="object")
    s = df[col].dropna().astype(str).str.strip()
    return s[s.ne("") & s.str.casefold().ne("nan")]


def parse_rating(series: pd.Series) -> pd.Series:
    # Survey skill ratings are on a 1–5 scale. Extract the first valid number only.
    values = pd.to_numeric(series, errors="coerce")
    text = series.astype(str).str.extract(r"(?<!\d)([1-5](?:\.\d+)?)(?!\d)", expand=False)
    values = values.fillna(pd.to_numeric(text, errors="coerce"))
    return values.where(values.between(1, 5))


def split_responses(series: pd.Series) -> pd.Series:
    """Split common multi-select exports while retaining readable category labels."""
    values = []
    for raw in series.dropna().astype(str):
        for part in re.split(r"[,;\n\r]+", raw):
            item = re.sub(r"\s+", " ", part).strip(" \t•-")
            if item and item.casefold() not in {"nan", "none", "n/a"}:
                values.append(item)
    return pd.Series(values, dtype="object")


def chart_theme(fig, height: int = 390):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=18, r=22, t=66, b=24),
        title=dict(font=dict(size=17, color="#202944", family="Manrope"), x=0.02, xanchor="left"),
        font=dict(family="DM Sans", size=12, color="#526078"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    # Explicitly style all Plotly text after layout updates so chart titles,
    # tick labels and axis titles remain readable against the light dashboard.
    fig.update_xaxes(
        showgrid=True, gridcolor="#edf0f6", zeroline=False, linecolor="#cbd3e1",
        tickfont=dict(family="DM Sans", size=12, color="#344054"),
        title_font=dict(family="DM Sans", size=13, color="#344054"),
    )
    fig.update_yaxes(
        showgrid=False, zeroline=False, linecolor="#cbd3e1",
        tickfont=dict(family="DM Sans", size=12, color="#344054"),
        title_font=dict(family="DM Sans", size=13, color="#344054"),
    )
    fig.update_layout(
        title_font=dict(family="Manrope", size=17, color="#192238"),
        font=dict(family="DM Sans", size=12, color="#344054"),
    )
    return fig


def count_chart(df: pd.DataFrame, col: Optional[str], title: str, *, multi: bool = False,
                top_n: int = 12, denominator: Optional[int] = None):
    if not col or col not in df.columns:
        st.info(f"This chart is unavailable because the matching survey column was not found: **{title}**.")
        return
    series = split_responses(df[col]) if multi else text_series(df, col)
    if series.empty:
        st.info(f"No usable responses were recorded for **{title}**.")
        return
    counts = series.value_counts().head(top_n).rename_axis("Response").reset_index(name="Respondents")
    denom = denominator or len(df)
    counts["% of survey sample"] = (counts["Respondents"] / max(denom, 1) * 100).round(1)
    counts = counts.sort_values("Respondents", ascending=True)
    fig = px.bar(counts, x="Respondents", y="Response", orientation="h", text="Respondents",
                 hover_data={"% of survey sample": True}, color_discrete_sequence=["#6c63df"])
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0, hovertemplate="%{y}<br>Responses: %{x}<extra></extra>")
    chart_theme(fig, max(300, 38 * len(counts) + 95))
    fig.update_layout(title=title, showlegend=False, xaxis_title="Number of responses", yaxis_title="")
    chart_theme(fig, max(300, 38 * len(counts) + 95))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
    with st.expander("View counts and percentages"):
        st.dataframe(counts.sort_values("Respondents", ascending=False), use_container_width=True, hide_index=True)


def render_hero():
    st.markdown(
        """
        <div class="hero">
          <h1>🎯 Career Aspiration &amp; Skill Gap Analysis for Youth</h1>
          <p>Turning student survey responses into clearer career direction, skill-development priorities and practical guidance for educational institutions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_heading(title: str, subtitle: str):
    st.title(title)
    st.markdown(f'<div class="section-intro">{subtitle}</div>', unsafe_allow_html=True)


def load_csv_bytes(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    # Try common encodings and delimiters without changing the source file.
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return clean_columns(pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=None, engine="python"))
        except Exception as exc:  # noqa: BLE001 - show one user-friendly error below
            last_error = exc
    raise ValueError(f"The file could not be read as a CSV. Details: {last_error}")


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    out = clean_columns(df)
    # Keep blank values blank; do not invent or impute survey responses.
    out = out.dropna(how="all").copy()
    return out


def split_count_table(df: pd.DataFrame, col: str, multi: bool = False) -> pd.DataFrame:
    series = split_responses(df[col]) if multi else text_series(df, col)
    if series.empty:
        return pd.DataFrame(columns=["Response", "Respondents", "Percent of sample"])
    counts = series.value_counts().rename_axis("Response").reset_index(name="Respondents")
    counts["Percent of sample"] = (counts["Respondents"] / max(len(df), 1) * 100).round(1)
    return counts


def make_action_recommendations(df: pd.DataFrame) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    skill_cols = [c for c in df.columns if SKILL_PREFIX.casefold() in c.casefold()]
    skill_rows = []
    for col in skill_cols:
        vals = parse_rating(df[col]).dropna()
        if not vals.empty:
            label = re.sub(re.escape(SKILL_PREFIX), "", col, flags=re.I).strip(" []")
            skill_rows.append((label, float(vals.mean()), int(vals.count())))
    if skill_rows:
        weakest = sorted(skill_rows, key=lambda x: x[1])[:3]
        names = ", ".join(f"{name} ({avg:.2f}/5)" for name, avg, _ in weakest)
        actions.append({"audience": "College / training providers", "title": "Prioritize skill practice", "body": f"The lowest average self-ratings in this sample are {names}. Consider practical workshops, guided exercises and small projects in these areas."})

    guidance_col = find_col(df, "sufficient career guidance")
    if guidance_col:
        vals = text_series(df, guidance_col).str.casefold()
        limited = int(vals.str.contains(r"very little|not at all|no", regex=True).sum())
        if limited:
            actions.append({"audience": "Career counsellors", "title": "Make guidance easier to access", "body": f"{limited} of {len(df)} respondents selected an answer indicating little or no career guidance. Consider regular drop-in sessions, career-path explainers and individual counselling."})

    internship_col = find_col(df, "completed an internship")
    if internship_col:
        vals = text_series(df, internship_col).str.casefold()
        no_internship = int(vals.str.startswith(("no", "not yet")).sum())
        if no_internship:
            actions.append({"audience": "Students / placement cells", "title": "Expand practical exposure", "body": f"{no_internship} respondents reported not having completed an internship. Share verified internship opportunities, project-based experience and portfolio-building activities."})

    support_col = find_col(df, "support would help you the most")
    if support_col:
        supports = split_responses(df[support_col])
        if not supports.empty:
            top = supports.value_counts().head(3)
            summary = ", ".join(f"{k} ({v} mentions)" for k, v in top.items())
            actions.append({"audience": "CEP / student support teams", "title": "Respond to stated support needs", "body": f"The most frequently mentioned support options are {summary}. Use these results to plan activities, then confirm demand with students before implementation."})

    if not actions:
        actions.append({"audience": "Project team", "title": "Validate priorities with students", "body": "Review the available responses with students and counsellors, then choose a small set of activities that can be delivered and evaluated."})
    return actions


# -----------------------------------------------------------------------------
# Navigation and upload flow
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<div style='font-size:.76rem;letter-spacing:.15em;font-weight:800;color:#b7b3ff;margin:8px 0 5px;'>CAREERLENS</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:1.18rem;font-weight:800;margin-bottom:18px;'>Youth Career Insights</div>", unsafe_allow_html=True)
    page = st.radio(
        "WORKSPACE",
        ["Upload & Overview", "Career Aspirations", "Skill Gap Analysis", "Guidance & Barriers", "Recommended Action Plan", "Explore Survey Data"],
        index=0,
        label_visibility="visible",
    )
    st.markdown("<hr style='border-color:#343851;margin:18px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700;margin-bottom:7px;'>Survey data</div>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload survey responses (.csv)", type=["csv"], key="sidebar_csv_upload", help="Upload the genuine CSV exported from your survey form.")
    st.caption("Use the original responses. This tool does not generate or add synthetic respondents.")
    if st.button("Clear loaded survey", use_container_width=True):
        st.session_state.pop("survey_df", None)
        st.session_state.pop("survey_source", None)
        st.rerun()

if uploaded is not None:
    try:
        st.session_state["survey_df"] = prepare_data(load_csv_bytes(uploaded))
        st.session_state["survey_source"] = f"Uploaded file: {uploaded.name}"
    except Exception as exc:  # noqa: BLE001
        st.error(f"We could not load this CSV. Please check that it is a valid, comma-separated survey export. {exc}")

# On the overview page, users may use the genuine bundled survey as a convenient demo source.
# This is the project's real 26-response export, not synthetic data.
if page == "Upload & Overview" and "survey_df" not in st.session_state:
    render_hero()
    render_page_heading("Start with your survey", "Upload the CSV exported from Google Forms. The application will validate the file and build the dashboard from the responses it contains.")
    left, right = st.columns([1.25, 0.75], gap="large")
    with left:
        st.markdown("<div class='insight-card'><span class='pill'>STEP 1</span><h4>Upload the survey export</h4><p>Use the CSV uploader in the left sidebar. Keep the original column headings where possible so the application can identify the survey questions reliably.</p><br><span class='mini-label'>Supported file</span><p>CSV · Google Forms response export</p></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='insight-card'><span class='pill'>WHAT HAPPENS NEXT</span><h4>Automatic analysis</h4><p>Column checks, missing-data review, career-interest charts, self-rated skill summaries, guidance and barrier analysis, and practical action suggestions.</p></div>", unsafe_allow_html=True)
    st.write("")
    if DEFAULT_CSV.exists():
        st.info("For a quick demonstration, you can load the project's included genuine survey export (26 responses). This uses the existing collected data and does not add simulated responses.")
        if st.button("Load included project survey", type="primary"):
            st.session_state["survey_df"] = prepare_data(pd.read_csv(DEFAULT_CSV))
            st.session_state["survey_source"] = "Included project survey export"
            st.rerun()
    st.markdown("<div class='footer-note'>CareerLens · CEP Topic 14 · Survey findings are descriptive and apply to the respondents in the uploaded sample.</div>", unsafe_allow_html=True)
    st.stop()

if "survey_df" not in st.session_state:
    st.warning("Please open **Upload & Overview** and upload a survey CSV before viewing the analysis pages.")
    st.stop()

df = st.session_state["survey_df"].copy()
source_label = st.session_state.get("survey_source", "Loaded survey")
if df.empty:
    st.error("The uploaded file contains no usable response rows. Please upload a valid survey export.")
    st.stop()

# Shared column mappings based on the actual survey question wording.
career_col = find_col(df, "career path are you most interested")
year_col = find_col(df, "current year of study")
field_col = find_col(df, "broad field best describes")
career_type_col = find_col(df, "type of career do you currently prefer")
clarity_col = find_col(df, "clear are you about your career goals")
work_col = find_col(df, "preferred work environment")
intern_col = find_col(df, "completed an internship")
cert_col = find_col(df, "completed any professional certification")
guidance_col = find_col(df, "sufficient career guidance")
challenge_col = find_col(df, "biggest challenge you currently face")
improve_col = find_col(df, "most need to improve")
support_col = find_col(df, "support would help you the most")
prepared_col = find_col(df, "adequately preparing you for employment")
confidence_col = find_col(df, "confident are you about getting an internship")
activity_col = find_col(df, "activities have you completed to prepare")
skill_cols = [c for c in df.columns if SKILL_PREFIX.casefold() in c.casefold()]


def render_overview():
    render_hero()
    st.caption(f"Data source: {source_label} · {len(df):,} response rows · {len(df.columns)} columns")
    st.markdown("### Survey at a glance")
    total = len(df)
    intern_yes = int(text_series(df, intern_col).str.casefold().str.startswith("yes").sum()) if intern_col else 0
    cert_yes = int(text_series(df, cert_col).str.casefold().str.startswith("yes").sum()) if cert_col else 0
    limited_guidance = int(text_series(df, guidance_col).str.casefold().str.contains(r"very little|not at all|no", regex=True).sum()) if guidance_col else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Survey responses", f"{total:,}")
    m2.metric("Reported internship", f"{intern_yes} / {total}", f"{intern_yes / total:.0%} of sample" if total else None)
    m3.metric("Course / certification", f"{cert_yes} / {total}", f"{cert_yes / total:.0%} of sample" if total else None)
    m4.metric("Little / no guidance", f"{limited_guidance} / {total}", f"{limited_guidance / total:.0%} of sample" if total else None)
    st.markdown("<div class='notice'><b>How to read these findings:</b> This is a descriptive analysis of the uploaded survey sample. It is not a representative estimate of all youth, and skill ratings are self-reported rather than objective skill tests.</div>", unsafe_allow_html=True)

    st.markdown("### What stands out in this sample")
    a, b = st.columns(2, gap="large")
    with a:
        count_chart(df, career_col, "Most selected career paths", top_n=8)
    with b:
        count_chart(df, year_col, "Respondents by year of study", top_n=8)
    c, d = st.columns(2, gap="large")
    with c:
        count_chart(df, field_col, "Current education fields", top_n=8)
    with d:
        count_chart(df, career_type_col, "Preferred career direction", top_n=8)

    st.markdown("### Data quality check")
    missing = df.isna().sum()
    quality = pd.DataFrame({"Survey column": df.columns, "Missing responses": missing.values,
                            "Missing (%)": (missing.values / max(len(df), 1) * 100).round(1)})
    q1, q2, q3 = st.columns(3)
    q1.metric("Columns", len(df.columns))
    q2.metric("Rows with at least one missing value", int(df.isna().any(axis=1).sum()))
    q3.metric("Blank cells", int(df.isna().sum().sum()))
    with st.expander("Inspect columns with the most missing responses"):
        st.dataframe(quality.sort_values("Missing responses", ascending=False).head(12), use_container_width=True, hide_index=True)
    st.caption("Missing answers are left missing; the app does not invent, impute or silently correct respondent data.")


def render_career():
    render_page_heading("Career aspirations", "Understand what respondents want to pursue, their preferred work direction and how clearly they describe their goals.")
    a, b = st.columns(2, gap="large")
    with a: count_chart(df, career_col, "Career paths respondents are most interested in", top_n=12)
    with b: count_chart(df, field_col, "Current education field", top_n=10)
    c, d = st.columns(2, gap="large")
    with c: count_chart(df, career_type_col, "Preferred career direction", top_n=10)
    with d: count_chart(df, work_col, "Preferred work environment", top_n=10)
    e, f = st.columns(2, gap="large")
    with e: count_chart(df, clarity_col, "Clarity about career goals", top_n=8)
    with f: count_chart(df, year_col, "Distribution by year of study", top_n=8)
    st.markdown("<div class='notice'><b>How this can be used:</b> Colleges can use the patterns to plan career talks, alumni sessions and career-path information for the fields represented in the sample. Avoid assuming that one career preference applies to every student.</div>", unsafe_allow_html=True)


def render_skills():
    render_page_heading("Skill gap analysis", "Compare self-rated confidence across career-related skills and identify areas that may benefit from practical development activities.")
    if not skill_cols:
        st.warning("No skill-rating columns were detected. Check that the CSV contains the original skill-rating question headers.")
        return
    rows = []
    for col in skill_cols:
        values = parse_rating(df[col]).dropna()
        label = re.sub(re.escape(SKILL_PREFIX), "", col, flags=re.I).strip(" []")
        if len(values):
            rows.append({"Skill": label, "Average self-rating": round(float(values.mean()), 2),
                         "Responses": int(values.count()), "Low ratings (1–2)": int(values.le(2).sum()),
                         "High ratings (4–5)": int(values.ge(4).sum())})
    if not rows:
        st.warning("Skill-rating columns were found, but no valid ratings between 1 and 5 could be parsed.")
        return
    skills = pd.DataFrame(rows).sort_values("Average self-rating", ascending=True)
    lowest = skills.iloc[0]
    highest = skills.sort_values("Average self-rating", ascending=False).iloc[0]
    a, b, c = st.columns(3)
    a.metric("Skills assessed", len(skills))
    b.metric("Lowest average rating", f"{lowest['Average self-rating']:.2f}/5", str(lowest["Skill"]))
    c.metric("Highest average rating", f"{highest['Average self-rating']:.2f}/5", str(highest["Skill"]))

    fig = px.bar(skills, x="Average self-rating", y="Skill", orientation="h", text="Average self-rating",
                 color="Average self-rating", color_continuous_scale=[[0,"#f59eae"],[0.5,"#a5b4fc"],[1,"#4f46e5"]],
                 hover_data=["Responses", "Low ratings (1–2)", "High ratings (4–5)"])
    fig.update_traces(texttemplate="%{x:.2f}", textposition="outside", cliponaxis=False)
    chart_theme(fig, max(450, len(skills) * 34 + 100))
    fig.update_layout(title="Average self-rated skill level · 1 = lowest, 5 = highest", xaxis=dict(range=[0, 5], title="Average rating"), yaxis_title="", coloraxis_showscale=False)
    chart_theme(fig, max(450, len(skills) * 34 + 100))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
    st.markdown("<div class='notice'><b>Interpretation:</b> Lower averages are possible training priorities, not proof of a measured skill deficit. Ratings reflect respondents' own confidence.</div>", unsafe_allow_html=True)
    st.markdown("### Skill summary")
    st.dataframe(skills.sort_values("Average self-rating"), use_container_width=True, hide_index=True)
    st.markdown("### Respondents' stated improvement areas")
    count_chart(df, improve_col, "Most selected improvement areas", multi=True, top_n=12)


def render_guidance():
    render_page_heading("Guidance & barriers", "Explore respondents' access to career guidance, perceived employment preparation, confidence and the barriers they report.")
    a, b = st.columns(2, gap="large")
    with a: count_chart(df, guidance_col, "Career guidance received", top_n=8)
    with b: count_chart(df, prepared_col, "Perceived employment preparation", top_n=8)
    c, d = st.columns(2, gap="large")
    with c: count_chart(df, confidence_col, "Confidence about obtaining a relevant internship or job", top_n=8)
    with d: count_chart(df, intern_col, "Internship experience", top_n=8)
    st.markdown("### Barriers and preparation activities")
    e, f = st.columns(2, gap="large")
    with e: count_chart(df, challenge_col, "Reported career challenges", multi=True, top_n=12)
    with f: count_chart(df, activity_col, "Career-preparation activities completed", multi=True, top_n=12)
    st.markdown("### Support requested by respondents")
    count_chart(df, support_col, "Most mentioned support options", multi=True, top_n=12)
    st.markdown("<div class='notice'><b>How this can be used:</b> Institutions can compare the most frequently reported barriers with the support options students select, then validate proposed activities with students before committing resources.</div>", unsafe_allow_html=True)


def render_actions():
    render_page_heading("Recommended action plan", "Practical options for turning survey patterns into student support. Recommendations are generated from available survey columns and should be reviewed before implementation.")
    actions = make_action_recommendations(df)
    for i, action in enumerate(actions, start=1):
        st.markdown(
            f"<div class='insight-card' style='margin-bottom:14px;'><span class='pill'>{action['audience']}</span><h4>{i:02d} · {action['title']}</h4><p>{action['body']}</p></div>",
            unsafe_allow_html=True,
        )
    st.markdown("### Suggested implementation cycle")
    steps = st.columns(4, gap="medium")
    step_data = [
        ("01", "Prioritize", "Select one or two needs supported by the survey."),
        ("02", "Co-design", "Ask students and relevant staff to refine the activity."),
        ("03", "Deliver", "Run a small workshop, counselling session or project activity."),
        ("04", "Evaluate", "Collect attendance and feedback; compare pre/post confidence if appropriate."),
    ]
    for col, (num, title, body) in zip(steps, step_data):
        with col:
            st.markdown(f"<div class='insight-card'><span class='pill'>STEP {num}</span><h4>{title}</h4><p>{body}</p></div>", unsafe_allow_html=True)
    st.caption("These are proposed actions, not evidence that the activities have already been conducted or proven effective.")


def render_explore():
    render_page_heading("Explore survey data", "Search and filter the uploaded responses. Identifying fields are hidden by default to reduce unnecessary exposure of personal information.")
    identifying = [c for c in df.columns if any(term in c.casefold() for term in IDENTIFYING_TERMS)]
    include_identifying = st.checkbox("Include identifying columns in the preview and download", value=False,
                                      help="Use only when necessary and with appropriate permission. This setting does not change the original file.")
    visible = df.copy() if include_identifying else df.drop(columns=identifying, errors="ignore").copy()
    c1, c2 = st.columns([1.4, 1])
    with c1:
        search = st.text_input("Search visible responses", placeholder="Search a career, skill, barrier or response…")
    with c2:
        filter_col = st.selectbox("Optional column filter", ["None"] + list(visible.columns))
    view = visible.copy()
    if search:
        mask = view.astype(str).apply(lambda s: s.str.contains(search, case=False, na=False, regex=False)).any(axis=1)
        view = view.loc[mask]
    if filter_col != "None":
        options = sorted(view[filter_col].dropna().astype(str).unique().tolist())
        selected = st.multiselect("Keep only selected values", options, default=[])
        if selected:
            view = view[view[filter_col].astype(str).isin(selected)]
    st.caption(f"Showing {len(view):,} of {len(df):,} response rows · {len(view.columns)} visible columns")
    st.dataframe(view, use_container_width=True, hide_index=True, height=480)
    st.download_button("Download filtered CSV", view.to_csv(index=False).encode("utf-8-sig"),
                       file_name="career_survey_filtered.csv", mime="text/csv", type="primary")
    with st.expander("Column completeness"):
        completeness = pd.DataFrame({"Column": df.columns, "Non-missing responses": df.notna().sum().values,
                                     "Missing responses": df.isna().sum().values,
                                     "Missing (%)": (df.isna().mean().values * 100).round(1)})
        st.dataframe(completeness.sort_values("Missing (%)", ascending=False), use_container_width=True, hide_index=True)


if page == "Upload & Overview":
    render_overview()
elif page == "Career Aspirations":
    render_career()
elif page == "Skill Gap Analysis":
    render_skills()
elif page == "Guidance & Barriers":
    render_guidance()
elif page == "Recommended Action Plan":
    render_actions()
elif page == "Explore Survey Data":
    render_explore()

st.markdown("<div class='footer-note'>CareerLens · Community Engagement Program · Topic 14 · Findings describe the uploaded sample only. Please verify recommendations before using them for institutional decisions.</div>", unsafe_allow_html=True)
