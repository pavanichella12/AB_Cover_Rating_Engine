"""
Main Streamlit App - Multi-Agent System with LangGraph Orchestration
Uses LangGraph for state management (blackboard pattern)
Login: SQLite + hashed passwords. Users with @abcover.org email can create an account or log in (auth.py).
"""

import base64
import hashlib
import os
import uuid
from typing import Optional, List, Tuple
import streamlit as st
import pandas as pd
from agents import LangGraphOrchestrator, AgentState, DataAnalysisAgent
from agents.data_cleaning_agent_llm import run_validation
from auth import init_db, check_credentials, create_user
from audit import setup_logging, init_audit_db, init_login_events_db, get_logger, log_run, log_error, log_login_success, log_login_failure, log_logout
from pdf_export import build_results_pdf
from dotenv import load_dotenv

load_dotenv()

# LangSmith: when LANGCHAIN_API_KEY is set, enable tracing so you can see full prompts/responses at smith.langchain.com
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "abcover")

# Logging (init early so we can log login)
setup_logging()
init_audit_db()
init_login_events_db()
logger = get_logger()

# Display: avoid PyArrow errors (e.g. "$150.00" converted to number) and cap large tables
DISPLAY_MAX_ROWS = 5000


def _dataset_fingerprint(df) -> str:
    """Lightweight fingerprint for versioning/audit: columns + row count (no full data)."""
    if df is None or not hasattr(df, "columns"):
        return ""
    cols = tuple(sorted(df.columns.astype(str).tolist()))
    n = len(df) if hasattr(df, "__len__") else 0
    h = hashlib.sha256(f"{cols}|{n}".encode()).hexdigest()[:16]
    return h


def _mapping_sanity_checks(column_map: dict) -> List[str]:
    """Sanity checks on column mapping for rating pipeline. Returns list of warning messages."""
    warnings = []
    stds = set(column_map.values()) if column_map else set()
    if "Date" not in stds and "School Year" not in stds:
        warnings.append("No column mapped to **Date** or **School Year**. Rating needs at least one to derive school year.")
    if "Employee Identifier" not in stds:
        warnings.append("No column mapped to **Employee Identifier**. Required for per-teacher calculations.")
    # Absence_Days can be computed from Duration / Start+End / Absence Type
    if "Absence_Days" not in stds and "Duration" not in stds and "Start Time" not in stds and "Absence Type" not in stds:
        warnings.append("No column mapped to **Absence_Days**, **Duration**, **Start Time**, or **Absence Type**. Absence days may be zero.")
    return warnings


def _dataframe_safe_for_display(df: pd.DataFrame, max_rows: Optional[int] = None) -> pd.DataFrame:
    """Return a copy safe for st.dataframe: all columns as string so PyArrow never fails (e.g. '$140.00' -> str). Optionally cap rows."""
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return df
    copy = df.copy()
    for col in copy.columns:
        copy[col] = copy[col].astype(str)
    if max_rows is not None and len(copy) > max_rows:
        copy = copy.head(max_rows)
    return copy

# Page configuration (must be first Streamlit command)
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "abcover_logo.png")
st.set_page_config(
    page_title="ABCover Rating Engine",
    page_icon=_LOGO_PATH if os.path.isfile(_LOGO_PATH) else "📊",
    layout="wide"
)

# Dark theme CSS (system fonts first so page loads fast; Google Fonts load async)
st.markdown("""
<style>
/* Prefer system fonts so first paint is fast; optional Google Fonts load later */
/* Logo box - light background so logo is visible on dark theme */
.abcover-logo-box {
    background: #ffffff;
    padding: 1.5rem 2rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.abcover-logo-box img { display: block; margin: 0 auto; }
.abcover-subtitle {
    font-size: 2.25rem;
    font-weight: 700;
    font-family: 'Boulder', 'Bodoni Moda', Georgia, serif;
    color: #0f172a !important;
    letter-spacing: -0.03em;
    margin-top: 0.75rem;
}
/* ABCover Rating Engine branding font */
h1, .abcover-brand { font-family: 'Bodoni Moda', Georgia, serif !important; }
/* Headers for dark theme */
h2, h3 {
    color: #fafafa !important;
    font-weight: 700 !important;
    font-family: 'DM Sans', sans-serif !important;
}
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.2rem !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Login state
# ---------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None

if not st.session_state.logged_in:
    init_db()
    st.title("🔐 ABCover Rating Engine")
    st.caption("Use your @abcover.org email to log in or create an account.")
    tab1, tab2 = st.tabs(["Log in", "Create account"])
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@abcover.org", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            if not (email and password):
                log_login_failure(email.strip() or "(empty)", "missing_fields")
                st.error("Please enter email and password.")
            elif not email.strip().lower().endswith("@abcover.org"):
                log_login_failure(email.strip().lower(), "invalid_domain")
                st.error("Only @abcover.org email addresses are allowed.")
            elif check_credentials(email.strip(), password):
                log_login_success(email.strip().lower())
                st.session_state.logged_in = True
                st.session_state.user_email = email.strip().lower()
                st.rerun()
            else:
                log_login_failure(email.strip().lower(), "invalid_password")
                st.error("Invalid email or password.")
    with tab2:
        with st.form("create_account_form"):
            new_email = st.text_input("Email", placeholder="you@abcover.org", key="signup_email")
            new_password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm password", type="password", key="signup_confirm")
            new_name = st.text_input("Name (optional)", placeholder="Your name", key="signup_name")
            create_submitted = st.form_submit_button("Create account")
        if create_submitted:
            if not (new_email and new_password):
                st.error("Please enter email and password.")
            elif not new_email.strip().lower().endswith("@abcover.org"):
                st.error("Only @abcover.org email addresses are allowed.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif create_user(new_email.strip(), new_password, new_name.strip()):
                st.success("Account created! Switch to the **Log in** tab and sign in.")
            else:
                st.error("This email is already registered. Log in instead.")
    st.stop()

# Logout in sidebar
with st.sidebar:
    st.caption(f"Logged in as **{st.session_state.user_email}**")
    # Show which LLM we're using (from env)
    _provider = (os.getenv("LLM_PROVIDER") or "google").strip().lower()
    _model = (os.getenv("LLM_MODEL") or "").strip() or None
    if _provider == "bedrock":
        st.caption("🤖 **LLM:** Bedrock / Claude 3.5 Sonnet")
    elif _provider == "anthropic":
        st.caption(f"🤖 **LLM:** Anthropic / {_model or 'Claude'}")
    elif _provider == "openai":
        st.caption(f"🤖 **LLM:** OpenAI / {_model or 'GPT-4'}")
    else:
        st.caption(f"🤖 **LLM:** Google / {_model or 'Gemini'}")
    if os.getenv("LANGCHAIN_API_KEY"):
        st.caption("📊 **LangSmith:** tracing on → [smith.langchain.com](https://smith.langchain.com)")
    if st.button("Log out"):
        log_logout(st.session_state.user_email or "")
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.rerun()

# ---------------------------------------------------------------------------
# Main app (only when logged in)
# ---------------------------------------------------------------------------
# Cache for column mapping (keyed by column names) - same columns = reuse AI result, no extra LLM call
if "_column_mapping_cache" not in st.session_state:
    st.session_state["_column_mapping_cache"] = {}

# Orchestrator is created lazily (only when we have uploaded data) so the first page load is fast.
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None

# Initialize state (blackboard)
if 'agent_state' not in st.session_state:
    st.session_state.agent_state: AgentState = {
        "raw_data": pd.DataFrame(),
        "selected_data": pd.DataFrame(),
        "cleaned_data": pd.DataFrame(),
        "data_analysis": {},
        "cleaning_reasoning": {},
        "cleaning_stats": {},
        "calculation_reasoning": {},
        "rating_results": {},
        "school_name": "",
        "selected_columns": [],
        "column_map": {},
        "suggested_column_map": None,
        "column_mapping_analyzed": False,
        "analyzed_for_columns": None,
        "column_display_names": {},
        "filters": {},
        "rating_inputs": {},
        "use_quick_mapping": False,
        "processing_history": []
    }

# Title with ABCover logo (centered, visible on dark theme)
def render_header():
    """Centered logo with Rating Engine Calculator below. Logo in light box for visibility on dark theme."""
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if os.path.isfile(_LOGO_PATH):
                with open(_LOGO_PATH, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                st.markdown(f"""
                <div class="abcover-logo-box">
                    <img src="data:image/png;base64,{b64}" width="180" alt="ABCover" />
                    <p class="abcover-subtitle">Rating Engine Calculator</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(
                    '<p class="abcover-subtitle">Rating Engine Calculator</p>',
                    unsafe_allow_html=True
                )
    st.markdown("---")

render_header()

# ============================================================================
# STEP 1: FILE UPLOAD
# ============================================================================
st.header("Step 1: Upload School Data File")
uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=['csv', 'xlsx', 'xls'],
    help="Upload your school absence history file"
)

if uploaded_file is not None:
    # Process file upload using orchestrator
    with st.spinner("Uploading and processing file..."):
        try:
            # Lazy-init orchestrator (and Bedrock/LLM) only when first needed
            if st.session_state.orchestrator is None:
                st.session_state.orchestrator = LangGraphOrchestrator()
            # Update state with uploaded file
            st.session_state.agent_state["uploaded_file"] = uploaded_file
            # Run upload node
            upload_result = st.session_state.orchestrator._upload_node(st.session_state.agent_state)
            
            # Update state with results
            for key, value in upload_result.items():
                st.session_state.agent_state[key] = value
            
            if not st.session_state.agent_state["raw_data"].empty:
                df = st.session_state.agent_state["raw_data"]
                logger.info("Upload success: file=%s rows=%s user=%s", getattr(uploaded_file, "name", ""), len(df), st.session_state.get("user_email"))
                st.success(f"✅ File uploaded successfully!")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rows", f"{len(df):,}")
                with col2:
                    st.metric("Columns", len(df.columns))
                with col3:
                    st.metric("Size", f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB")
                
                # Show blackboard context
                with st.expander("📋 Blackboard State (Shared Memory)", expanded=False):
                    st.write("**Raw Data:** Available")
                    st.write(f"**Rows:** {len(df):,}")
                    st.write(f"**Columns:** {', '.join(df.columns.tolist()[:5])}...")
                
                st.markdown("---")
        except Exception as e:
            log_error("upload", e, user_email=st.session_state.get("user_email"), filename=getattr(uploaded_file, "name", None))
            st.error(f"❌ Upload error: {str(e)}")

# Standard column names (for mapping - so your team sees consistent names)
STANDARD_COLUMNS = [
    "School Year",
    "Employee Identifier",
    "Employee First Name",
    "Employee Last Name",
    "Absence_Days",
    "Date",
    "School Name",
    "Reason",
    "Employee Title",
    "Employee Type",
    "Absence Type",
    "Start Time",
    "End Time",
    "Filled",
    "Needs Substitute",
]

# Fallback alias mapping (when agent returns none) - same logic as orchestrator
# NOTE: Do NOT map "duration" to Absence_Days - Duration is HOURS (e.g. 7.5), Absence_Days must be days.
# Cleaning agent calculates Absence_Days from Absence Type + Duration (Full=1.0, Half=0.5, Custom=hrs/7.5).
COLUMN_ALIASES = {
    "school year": "School Year", "schoolyear": "School Year", "sy": "School Year",
    "employee identifier": "Employee Identifier", "employee id": "Employee Identifier",
    "emp id": "Employee Identifier", "employee_id": "Employee Identifier",
    "employee first name": "Employee First Name", "first name": "Employee First Name",
    "employee first": "Employee First Name", "first": "Employee First Name",
    "employee last name": "Employee Last Name", "last name": "Employee Last Name",
    "employee last": "Employee Last Name", "last": "Employee Last Name",
    "absence_days": "Absence_Days", "absence days": "Absence_Days",
    "percent of day": "Absence_Days",  # Percent of Day is already in days (1.0, 0.5)
    "date": "Date", "school name": "School Name", "reason": "Reason",
    "employee title": "Employee Title", "employee type": "Employee Type",
    "absence type": "Absence Type", "start time": "Start Time", "end time": "End Time",
    "filled": "Filled",
    "is filled": "Filled",
    "needs substitute": "Needs Substitute",
    "substitute is required": "Needs Substitute",
}


def _fallback_column_mapping(df, standard_cols):
    """When agent returns empty, use alias matching so user still sees mappings."""
    out = {}
    for c in df.columns:
        c_str = str(c).strip().lower()
        c_nospace = c_str.replace(" ", "").replace("_", "")
        for alias, std in COLUMN_ALIASES.items():
            if std not in standard_cols:
                continue
            # Never map Hire Date to Date - Hire Date = hire date, Date = absence date
            if std == "Date" and ("hire" in c_str or "hiredate" in c_nospace):
                continue
            if c_str == alias or c_nospace == alias.replace(" ", "").replace("_", ""):
                out[c] = std
                break
            if alias in c_str or c_str in alias:
                if std == "Date" and ("hire" in c_str or "hiredate" in c_nospace):
                    continue
                out[c] = std
                break
    return out

# ============================================================================
# STEP 2: DATA SELECTION
# ============================================================================
if not st.session_state.agent_state["raw_data"].empty:
    st.header("Step 2: Select Columns and Filter Rows")
    
    df_raw = st.session_state.agent_state["raw_data"]
    raw_cols = tuple(df_raw.columns.tolist())
    analyzed_for = st.session_state.agent_state.get("analyzed_for_columns")
    if analyzed_for != raw_cols:
        st.session_state.agent_state["column_mapping_analyzed"] = False
        st.session_state.agent_state["analyzed_for_columns"] = None
    
    if not st.session_state.agent_state.get("column_mapping_analyzed"):
        # Check cache: same column set = reuse previous AI result (no LLM call)
        cache = st.session_state["_column_mapping_cache"]
        if raw_cols in cache:
            suggested = cache[raw_cols]
            st.session_state.agent_state["suggested_column_map"] = suggested
            st.session_state.agent_state["column_mapping_analyzed"] = True
            st.session_state.agent_state["analyzed_for_columns"] = raw_cols
            st.caption("Column mapping loaded from cache (same file structure).")
            st.rerun()
        with st.spinner("🤖 Agent analyzing columns and mapping to standard names..."):
            try:
                provider = (os.getenv("LLM_PROVIDER") or "google").strip().lower()
                model_name = (os.getenv("LLM_MODEL") or "").strip() or None
                analysis_agent = DataAnalysisAgent(model_provider=provider, model_name=model_name)
                suggested = analysis_agent.suggest_column_mapping(df_raw, STANDARD_COLUMNS)
                if not suggested:
                    suggested = _fallback_column_mapping(df_raw, STANDARD_COLUMNS)
                    if suggested:
                        st.caption("Agent returned none; using fallback alias mapping.")
                st.session_state.agent_state["suggested_column_map"] = suggested
                st.session_state.agent_state["column_mapping_analyzed"] = True
                st.session_state.agent_state["analyzed_for_columns"] = raw_cols
                cache[raw_cols] = suggested  # cache for next time same columns are seen
            except Exception as e:
                suggested = _fallback_column_mapping(df_raw, STANDARD_COLUMNS)
                st.session_state.agent_state["suggested_column_map"] = suggested
                st.session_state.agent_state["column_mapping_analyzed"] = True
                st.session_state.agent_state["analyzed_for_columns"] = raw_cols
                cache[raw_cols] = suggested  # cache fallback too
                st.warning(f"Agent error: {e}. Using fallback alias mapping.")
        st.rerun()
    
    # Column selection
    available_columns = df_raw.columns.tolist()
    # Default: exclude Hire Date (not needed for rating; often confused with absence Date)
    def _is_hire_date(col):
        n = str(col).strip().lower().replace(" ", "").replace("_", "")
        return n == "hiredate"
    default_cols = [c for c in available_columns if not _is_hire_date(c)]
    if not default_cols:
        default_cols = available_columns
    selected_columns = st.multiselect(
        "Select columns to keep:",
        options=available_columns,
        default=default_cols,
        help="Choose which columns to include. Hire Date is excluded by default (not needed for rating)."
    )
    
    # Mapping: AI suggestion first, then user can override with dropdowns per standard
    st.subheader("Column mapping")
    suggested_map = st.session_state.agent_state.get("suggested_column_map") or {}
    def _is_valid_mapping(col: str, std: str) -> bool:
        c_lower = str(col).strip().lower().replace(" ", "").replace("_", "")
        return not (std == "Date" and ("hire" in c_lower or "hiredate" in c_lower))
    suggested_column_map = {col: suggested_map[col] for col in selected_columns if col in suggested_map and suggested_map[col] in STANDARD_COLUMNS and _is_valid_mapping(col, suggested_map[col])}
    # Standards we let the user assign to a column (so different file formats are no hassle)
    MAPPABLE_STANDARDS = [
        "School Year", "Employee Identifier", "Date", "Absence_Days", "Absence Type",
        "Employee Type", "Employee First Name", "Employee Last Name",
        "Reason", "Employee Title", "School Name", "Filled", "Needs Substitute",
        "Start Time", "End Time", "Duration",
    ]
    # Dropdown per standard: "Which column is [Standard]?"
    st.caption("**Choose which column is what** — so different file formats work. AI suggestion is the default; change if needed.")
    column_choices = {}
    opts = ["— Don't map —"] + sorted(selected_columns)
    for std in MAPPABLE_STANDARDS:
        current = next((c for c, s in suggested_column_map.items() if s == std), None)
        idx = opts.index(current) if current and current in opts else 0
        choice = st.selectbox(
            f"**{std}**",
            options=opts,
            index=idx,
            key=f"map_sel_{std}",
            help=f"Which of your columns should be used as {std}?"
        )
        if choice and choice != "— Don't map —":
            column_choices[choice] = std
    # Final map: user choices override; then add any suggested mappings for columns not chosen by user
    column_map = dict(column_choices)
    for col in selected_columns:
        if col not in column_map and col in suggested_map and suggested_map[col] in STANDARD_COLUMNS and _is_valid_mapping(col, suggested_map[col]):
            column_map[col] = suggested_map[col]
    unmapped_columns = [col for col in selected_columns if col not in column_map]
    
    if column_map:
        with st.expander("📋 View mapping summary", expanded=False):
            for orig, std in sorted(column_map.items(), key=lambda x: x[1]):
                st.write(f"*{orig}* → **{std}**")
    if unmapped_columns:
        st.caption(f"Columns kept as-is (no standard name): {', '.join(f'*{c}*' for c in unmapped_columns)}")
    # Sanity checks on mapping (e.g. Date/School Year, Employee Identifier, days source)
    mapping_warnings = _mapping_sanity_checks(column_map)
    if mapping_warnings:
        for w in mapping_warnings:
            st.warning(w)
    with st.expander("How is Absence_Days (no. of days) calculated?", expanded=False):
        st.caption("Calculated in Step 3 (Cleaning). **We focus on Duration and times** (Absence Type is often reason for leave, e.g. Sick/Personal):")
        st.markdown("1. If you mapped a **days** column → we use it.")
        st.markdown("2. Else **Duration (hours)** → days = Duration ÷ 7.5")
        st.markdown("3. Else **Start Time** and **End Time** → hours between them ÷ 7.5")
        st.markdown("4. Else if Absence Type is **Full Day** / **Half Day** / **Custom Duration** → we use that.")
        st.caption("So map **Duration** (and optionally **Start Time** / **End Time**) when your file has them; Absence Type can stay as reason for leave.")
    
    # Row filters (optional)
    with st.expander("🔍 Row Filters (Optional)"):
        # No date range filter - use test logic: Rule 3 in cleaning validates Date within School Year (July 1 - June 30)
        if 'Date' in available_columns:
            date_col = df_raw['Date']
            try:
                dt = pd.to_datetime(date_col, errors='coerce')
                min_d, max_d = dt.min(), dt.max()
                if pd.notna(min_d) and pd.notna(max_d):
                    st.caption(f"📅 Dates in data: {min_d.strftime('%Y-%m-%d')} to {max_d.strftime('%Y-%m-%d')} (filtered by School Year in cleaning)")
            except Exception:
                pass
        
        # Employee type filter: use the raw column that maps TO "Employee Type" (e.g. "Class Description")
        # Use chips + Remove buttons so the list doesn't jump to the end when you remove an item (multiselect scroll bug).
        employee_type_raw_col = next((orig for orig, std in column_map.items() if std == "Employee Type"), None)
        if employee_type_raw_col and employee_type_raw_col in df_raw.columns:
            employee_types = df_raw[employee_type_raw_col].dropna().astype(str).unique().tolist()
            employee_types = sorted([x for x in employee_types if x.strip()])
        elif 'Employee Type' in available_columns:
            employee_types = df_raw['Employee Type'].dropna().astype(str).unique().tolist()
            employee_types = sorted([x for x in employee_types if x.strip()])
        else:
            employee_types = []

        if employee_types:
            # Persist selection in session state so removing one doesn't scroll the list
            opts_key = "step2_emp_types_opts"
            sel_key = "step2_emp_types_selected"
            # Compare by content (tuple) so we only reset when the actual options change (e.g. new file), not every run
            opts_tuple = tuple(employee_types)
            if opts_key not in st.session_state or st.session_state[opts_key] != opts_tuple:
                st.session_state[opts_key] = opts_tuple
                st.session_state[sel_key] = list(employee_types)
            selected_employee_types = st.session_state[sel_key]

            def _remove_emp_type(et):
                if sel_key in st.session_state:
                    st.session_state[sel_key] = [x for x in st.session_state[sel_key] if x != et]

            st.caption(f"From column « {employee_type_raw_col or 'Employee Type'} » (mapped to Employee Type). Remove types to exclude from filter.")
            # Stable list (sorted): each row has label + Remove; use on_click so removal persists
            for i, et in enumerate(sorted(selected_employee_types)):
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.text(et)
                with col2:
                    key_safe = "rem_et_%d_%s" % (i, "".join(c if c.isalnum() or c == "_" else "_" for c in str(et))[:50])
                    st.button("✕ Remove", key=key_safe, on_click=_remove_emp_type, args=(et,))

            # Add back: multiselect of currently excluded types + button
            excluded = [x for x in employee_types if x not in selected_employee_types]
            if excluded:
                add_back = st.multiselect("Add back (currently excluded):", options=excluded, default=[], key="step2_emp_add_back")
                if st.button("Add selected", key="step2_emp_add_btn") and add_back:
                    st.session_state[sel_key] = sorted(set(st.session_state[sel_key]) | set(add_back))
                    if "step2_emp_add_back" in st.session_state:
                        st.session_state["step2_emp_add_back"] = []
                    st.rerun()
        else:
            selected_employee_types = None
    
    # Apply selection
    if st.button("Apply Selection", type="primary"):
        filters = {}
        # No date_range filter - Rule 3 in cleaning validates Date within School Year
        if selected_employee_types:
            filters['employee_type'] = selected_employee_types
        
        # Update state (including column mapping and display names for "both names" view)
        st.session_state.agent_state["selected_columns"] = selected_columns
        st.session_state.agent_state["column_map"] = column_map
        st.session_state.agent_state["column_display_names"] = {
            std: f"{std} ({orig})" for orig, std in column_map.items()
        }
        st.session_state.agent_state["filters"] = filters
        
        # Run select node
        with st.spinner("Selecting data..."):
            try:
                if st.session_state.orchestrator is None:
                    st.session_state.orchestrator = LangGraphOrchestrator()
                select_state = st.session_state.agent_state.copy()
                select_result = st.session_state.orchestrator._select_node(select_state)
                st.session_state.agent_state.update(select_result)
                
                if not st.session_state.agent_state["selected_data"].empty:
                    df_selected = st.session_state.agent_state["selected_data"]
                    fn = getattr(st.session_state.agent_state.get("uploaded_file"), "name", "")
                    logger.info("Select success: file=%s rows=%s cols=%s user=%s", fn, len(df_selected), len(selected_columns), st.session_state.get("user_email"))
                    st.success(f"✅ Selected {len(df_selected):,} rows with {len(selected_columns)} columns")
                    # Preview with both names (standard + original) if we have mappings
                    disp = st.session_state.agent_state.get("column_display_names", {})
                    if disp:
                        df_show = df_selected.rename(columns={k: v for k, v in disp.items() if k in df_selected.columns})
                        with st.expander("📊 Preview (Standard name ← School name)", expanded=False):
                            st.caption("Columns show: **Our standard name** (school column name)")
                            total = len(df_show)
                            preview = _dataframe_safe_for_display(df_show, max_rows=DISPLAY_MAX_ROWS)
                            st.dataframe(preview, width="stretch", hide_index=True)
                            if total > DISPLAY_MAX_ROWS:
                                st.caption(f"Showing first {DISPLAY_MAX_ROWS:,} of {total:,} rows.")
                            st.download_button("Download full selected data (CSV)", df_show.to_csv(index=False).encode("utf-8"), file_name="selected_data.csv", mime="text/csv", key="dl_selected")
                    # Show blackboard context
                    with st.expander("📋 Blackboard State", expanded=False):
                        st.write("**Raw Data:** Available")
                        st.write("**Selected Data:** Available")
                        st.write(f"**Selected Rows:** {len(df_selected):,}")
                    
                    st.markdown("---")
            except Exception as e:
                state = st.session_state.agent_state
                log_error("select", e, user_email=st.session_state.get("user_email"),
                    filename=getattr(state.get("uploaded_file"), "name", None),
                    rows_raw=len(state.get("raw_data", [])) if hasattr(state.get("raw_data"), "__len__") else None)
                st.error(f"❌ Selection error: {str(e)}")

# ============================================================================
# STEP 3: DATA CLEANING (LLM-Powered)
# ============================================================================
if not st.session_state.agent_state["selected_data"].empty:
    st.header("Step 3: Data Cleaning (LLM-Powered)")
    selected_data = st.session_state.agent_state["selected_data"]

    # First-class data validation (before cleaning): show report so user sees what will be checked
    validation_key = "step3_validation_report"
    df_fingerprint = _dataset_fingerprint(selected_data)
    if validation_key not in st.session_state or st.session_state.get("step3_validation_df_id") != df_fingerprint:
        try:
            _, report = run_validation(selected_data)
            st.session_state[validation_key] = report
            st.session_state["step3_validation_df_id"] = df_fingerprint
        except Exception as e:
            st.session_state[validation_key] = {"format_issues": [str(e)], "rows_removed": 0, "columns_checked": [], "data_type_issues": [], "invalid_values": [], "final_rows": len(selected_data)}
    with st.expander("📋 Data Validation (before cleaning)", expanded=True):
        report = st.session_state.get(validation_key, {})
        st.caption("Checks: required columns, data types, date format, empty rows, invalid values.")
        if report.get("format_issues"):
            for msg in report["format_issues"]:
                st.warning(msg)
        if report.get("data_type_issues"):
            for msg in report["data_type_issues"]:
                st.warning(msg)
        if report.get("invalid_values"):
            for msg in report["invalid_values"]:
                st.warning(msg)
        if report.get("columns_checked"):
            st.caption(f"Columns checked: {', '.join(report['columns_checked'])}")
        st.caption(f"Rows after validation: {report.get('final_rows', len(selected_data)):,} (removed: {report.get('rows_removed', 0):,})")

    # Get school name
    school_name = st.text_input(
        "School Name (optional, helps LLM reasoning):", 
        value=st.session_state.agent_state.get("school_name", ""),
        key="school_name_input"
    )
    
    if st.button("Clean Data", type="primary"):
        # Update state
        st.session_state.agent_state["school_name"] = school_name
        
        _provider = (os.getenv("LLM_PROVIDER") or "google").strip().lower()
        _llm_label = "Bedrock (Claude Sonnet)" if _provider == "bedrock" else (_provider if _provider else "LLM")
        with st.spinner(f"🤖 Calling {_llm_label} — analyzing data and cleaning rules (may take 1–2 min)..."):
            try:
                # Run clean node (LLM-powered)
                if st.session_state.orchestrator is None:
                    st.session_state.orchestrator = LangGraphOrchestrator()
                clean_state = st.session_state.agent_state.copy()
                clean_result = st.session_state.orchestrator._clean_node(clean_state)
                st.session_state.agent_state.update(clean_result)
                
                if not st.session_state.agent_state["cleaned_data"].empty:
                    df_cleaned = st.session_state.agent_state["cleaned_data"]
                    df_sel = st.session_state.agent_state["selected_data"]
                    fn = getattr(st.session_state.agent_state.get("uploaded_file"), "name", "")
                    logger.info("Clean success: file=%s before=%s after=%s user=%s", fn, len(df_sel), len(df_cleaned), st.session_state.get("user_email"))
                    st.success("✅ Data cleaned successfully!")
                    # Preview cleaned data with both names
                    disp = st.session_state.agent_state.get("column_display_names", {})
                    df_cleaned = st.session_state.agent_state["cleaned_data"]
                    if disp:
                        df_show = df_cleaned.rename(columns={k: v for k, v in disp.items() if k in df_cleaned.columns})
                        with st.expander("📊 Preview cleaned data (Standard name ← School name)", expanded=False):
                            st.caption("Columns show: **Our standard name** (school column name)")
                            total = len(df_show)
                            preview = _dataframe_safe_for_display(df_show, max_rows=DISPLAY_MAX_ROWS)
                            st.dataframe(preview, width="stretch", hide_index=True)
                            if total > DISPLAY_MAX_ROWS:
                                st.caption(f"Showing first {DISPLAY_MAX_ROWS:,} of {total:,} rows.")
                            st.download_button("Download full cleaned data (CSV)", df_show.to_csv(index=False).encode("utf-8"), file_name="cleaned_data.csv", mime="text/csv", key="dl_cleaned")
                    # Show cleaning stats (we need to get this from the agent)
                    df_cleaned = st.session_state.agent_state["cleaned_data"]
                    df_selected = st.session_state.agent_state["selected_data"]
                    
                    st.subheader("📊 Cleaning Statistics")
                    cstats = st.session_state.agent_state.get("cleaning_stats") or {}
                    if cstats.get("rule1_columns_detected") is False:
                        st.warning(
                            "Rule 1 (drop **unfilled + substitute not required**) was skipped: "
                            "selected data has no **Filled** + **Needs Substitute** (or Ecorse-style equivalents). "
                            "In Step 2, include those columns and map them to **Filled** and **Needs Substitute**."
                        )
                    with st.expander("Row counts after each cleaning step", expanded=False):
                        st.write(
                            {
                                "After validation": cstats.get("after_validation"),
                                "After Rule 1 (substitute relevance)": cstats.get("after_rule1"),
                                "After Rule 2 (employee types)": cstats.get("after_rule2"),
                                "After Rule 3 (dates in school year)": cstats.get("after_rule3"),
                                "Final": cstats.get("final_rows"),
                            }
                        )
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Before Cleaning", f"{len(df_selected):,} rows")
                    with col2:
                        st.metric("After Cleaning", f"{len(df_cleaned):,} rows")
                    
                    # Show blackboard context
                    with st.expander("📋 Blackboard State", expanded=False):
                        st.write("**Raw Data:** Available")
                        st.write("**Selected Data:** Available")
                        st.write("**Cleaned Data:** Available")
                        st.write("**Cleaning Reasoning:** Available")
                    
                    st.markdown("---")
            except Exception as e:
                state = st.session_state.agent_state
                raw = state.get("raw_data")
                sel = state.get("selected_data")
                log_error("clean", e, user_email=st.session_state.get("user_email"),
                    filename=getattr(state.get("uploaded_file"), "name", None),
                    rows_raw=len(raw) if raw is not None and hasattr(raw, "__len__") else None,
                    rows_selected=len(sel) if sel is not None and hasattr(sel, "__len__") else None)
                st.error(f"❌ Cleaning error: {str(e)}")

# ============================================================================
# STEP 4: RATING ENGINE CALCULATOR (LLM-Powered)
# ============================================================================
if not st.session_state.agent_state["cleaned_data"].empty:
    st.header("Step 4: Rating Engine Calculator (LLM-Powered)")
    
    # Input variables
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Input Variables")
        school_district = st.text_input("School District Name:", value="")
        school_year_days = st.number_input("School Year Days:", min_value=1, value=180, step=1)
        replacement_cost = st.number_input("Replacement Cost per Day ($):", min_value=0.0, value=150.0, step=1.0)
        deductible = st.number_input("Deductible (Days):", min_value=0, value=20, step=1)
    
    with col2:
        st.subheader("Coverage & Commission")
        cc_days = st.number_input("CC Days (per teacher):", min_value=0, value=60, step=1)
        ark_commission = st.number_input("Carrier Profit Margin (%):", min_value=0.0, max_value=100.0, value=15.0, step=0.1) / 100
        abcover_commission = st.number_input("ABCover Acquisition Costs (%):", min_value=0.0, max_value=100.0, value=15.0, step=0.1) / 100
    
    # Edge-case note: 0 deductible / 0 CC days are valid and handled correctly
    if deductible == 0 or cc_days == 0:
        cc_max_preview = int(deductible) + int(cc_days)
        if deductible == 0 and cc_days > 0:
            st.caption("✓ **Deductible = 0:** All staff with 1+ absence days are in the CC range (1–{}) for premium. Staff with 0 days are below deductible.".format(cc_max_preview))
        elif cc_days == 0:
            st.caption("✓ **CC Days = 0:** CC Maximum = {}; no staff in CC range, so premium will be $0. High claimants are staff with days > {}.".format(cc_max_preview, cc_max_preview))
    
    # Calculate button
    if st.button("Calculate Premium", type="primary", use_container_width=True):
        # Versioning: generate run_id for this calculation (reproducibility / audit)
        st.session_state["_run_id"] = str(uuid.uuid4())
        # Update state with rating inputs
        st.session_state.agent_state["rating_inputs"] = {
            "deductible": int(deductible),
            "cc_days": int(cc_days),
            "replacement_cost": float(replacement_cost),
            "ark_commission_rate": float(ark_commission),
            "abcover_commission_rate": float(abcover_commission),
            "school_year_days": int(school_year_days) if school_year_days else None
        }
        
        _provider_calc = (os.getenv("LLM_PROVIDER") or "google").strip().lower()
        _llm_label_calc = "Bedrock (Claude Sonnet)" if _provider_calc == "bedrock" else (_provider_calc if _provider_calc else "LLM")
        with st.spinner(f"🤖 Calling {_llm_label_calc} — reasoning about calculations (may take 1–2 min)..."):
            try:
                # Run calculate node (LLM-powered)
                if st.session_state.orchestrator is None:
                    st.session_state.orchestrator = LangGraphOrchestrator()
                calc_state = st.session_state.agent_state.copy()
                calc_result = st.session_state.orchestrator._calculate_node(calc_state)
                st.session_state.agent_state.update(calc_result)
                
                if st.session_state.agent_state.get("rating_results"):
                    st.success("✅ Calculations complete!")
                    # Audit: record successful run (with run_id, model, dataset fingerprint for reproducibility)
                    state = st.session_state.agent_state
                    res = state.get("rating_results", {})
                    cleaned = state.get("cleaned_data")
                    log_run(
                        status="success",
                        user_email=st.session_state.get("user_email"),
                        filename=getattr(state.get("uploaded_file"), "name", None),
                        filters=state.get("filters"),
                        rows_raw=len(state.get("raw_data")) if state.get("raw_data") is not None else None,
                        rows_selected=len(state.get("selected_data")) if state.get("selected_data") is not None else None,
                        rows_cleaned=len(cleaned) if cleaned is not None else None,
                        total_teachers=res.get("overall_total_staff") or res.get("total_teachers"),
                        total_premium=res.get("total_premium"),
                        run_id=st.session_state.get("_run_id"),
                        model_name=(os.getenv("LLM_MODEL") or os.getenv("LLM_PROVIDER") or "default").strip() or None,
                        dataset_fingerprint=_dataset_fingerprint(cleaned),
                    )
                    logger.info("Calculate success: user=%s premium=%s", st.session_state.get("user_email"), res.get("total_premium"))
                    # Show blackboard context
                    with st.expander("📋 Blackboard State (Full Context)", expanded=False):
                        state = st.session_state.agent_state
                        st.write("**All Data Available:**")
                        st.write(f"- Raw Data: {len(state['raw_data']):,} rows")
                        st.write(f"- Selected Data: {len(state['selected_data']):,} rows")
                        st.write(f"- Cleaned Data: {len(state['cleaned_data']):,} rows")
                        st.write(f"- Cleaning Reasoning: Available")
                        st.write(f"- Calculation Reasoning: Available")
                        st.write(f"- Results: Available")
                        st.write(f"\n**Processing History:** {len(state['processing_history'])} steps")
                    
                    st.markdown("---")
            except Exception as e:
                state = st.session_state.agent_state
                raw = state.get("raw_data")
                sel = state.get("selected_data")
                clean = state.get("cleaned_data")
                log_error("calculate", e, user_email=st.session_state.get("user_email"),
                    filename=getattr(state.get("uploaded_file"), "name", None),
                    filters=state.get("filters"),
                    rows_raw=len(raw) if raw is not None and hasattr(raw, "__len__") else None,
                    rows_selected=len(sel) if sel is not None and hasattr(sel, "__len__") else None,
                    rows_cleaned=len(clean) if clean is not None and hasattr(clean, "__len__") else None,
                    run_id=st.session_state.get("_run_id"),
                    model_name=(os.getenv("LLM_MODEL") or os.getenv("LLM_PROVIDER") or "default").strip() or None,
                    dataset_fingerprint=_dataset_fingerprint(clean),
                )
                st.error(f"❌ Calculation error: {str(e)}")

# ============================================================================
# STEP 5: RESULTS DISPLAY
# ============================================================================
if st.session_state.agent_state.get("rating_results"):
    st.header("Step 5: Results")
    results = st.session_state.agent_state["rating_results"]
    rating_inputs = st.session_state.agent_state.get("rating_inputs", {})

    # PDF download: save Final Calculation Results as PDF
    try:
        pdf_bytes = build_results_pdf(results, rating_inputs)
        st.download_button(
            label="📥 Download / Save PDF",
            data=pdf_bytes,
            file_name="ABCover_Calculation_Results.pdf",
            mime="application/pdf",
            type="primary",
            key="download_results_pdf",
        )
    except Exception as e:
        st.caption(f"PDF export unavailable: {e}")
    
    # Get inputs for display
    replacement_cost = rating_inputs.get("replacement_cost", results.get("replacement_cost", 150.0))
    school_year_days = rating_inputs.get("school_year_days", results.get("school_year_days", 180))
    deductible = results.get("deductible", rating_inputs.get("deductible", 20))
    cc_days = results.get("cc_days", rating_inputs.get("cc_days", 60))
    cc_maximum = results.get("cc_maximum", deductible + cc_days)
    ark_rate = rating_inputs.get("ark_commission_rate", 0.15)
    abcover_rate = rating_inputs.get("abcover_commission_rate", 0.15)
    avg_metrics = None  # set from Calculation Breakdown by School Year when available; used in Coverage Metrics & Premium

    # ============================================================================
    # PER-SCHOOL-YEAR METRICS TABLE (Like Excel)
    # ============================================================================
    if results.get("per_school_year_metrics"):
        st.subheader("📊 School Year Metrics (From Cleaned Data)")
        
        table_data = []
        total_staff_sum = 0
        total_absences_sum = 0
        total_replacement_cost_sum = 0
        school_year_count = 0
        per_school_year_metrics = results["per_school_year_metrics"]
        sorted_school_years = sorted(per_school_year_metrics.keys())
        
        for school_year in sorted_school_years:
            metrics = per_school_year_metrics[school_year]
            table_data.append({
                "School Year": school_year,
                "Total # Of Staff": f"{metrics['total_staff']:,}",
                "Total # of Absences": f"{metrics['total_absences']:,.2f}",
                "Replacement Cost Per Day ($)": f"${replacement_cost:.2f}",
                "Total Replacement Cost to District ($)": f"${metrics['total_replacement_cost']:,.2f}",
                "Amt. of School Year Days": school_year_days,
                "Deductible (Days)": deductible,
                "CC Max (Days)": cc_days
            })
            total_staff_sum += metrics['total_staff']
            total_absences_sum += metrics['total_absences']
            total_replacement_cost_sum += metrics['total_replacement_cost']
            school_year_count += 1
        
        if school_year_count > 1:
            avg_staff = total_staff_sum / school_year_count
            avg_absences = total_absences_sum / school_year_count
            avg_replacement_cost = total_replacement_cost_sum / school_year_count
            table_data.append({
                "School Year": "5-Yr Avg",
                "Total # Of Staff": f"{avg_staff:,.1f}",
                "Total # of Absences": f"{avg_absences:,.1f}",
                "Replacement Cost Per Day ($)": f"${replacement_cost:.2f}",
                "Total Replacement Cost to District ($)": f"${avg_replacement_cost:,.2f}",
                "Amt. of School Year Days": school_year_days,
                "Deductible (Days)": deductible,
                "CC Max (Days)": cc_days
            })
        
        st.dataframe(_dataframe_safe_for_display(pd.DataFrame(table_data)), width="stretch", hide_index=True)
        st.info(f"📊 **Overall (Cumulative over 5 years):** {results.get('overall_total_staff', 0):,} staff, {results.get('overall_total_absences', 0):,.2f} absences, ${results.get('overall_total_replacement_cost', 0):,.2f} total replacement cost")
        with st.expander("❓ How are these numbers calculated? How do I verify?"):
            st.markdown("""
            **Total # of Absences** (per school year) is the **sum of absence days** in cleaned data for that year, not the number of rows.
            - Each row has an **Absence_Days** value: **Full Day = 1.0**, **AM/PM Half Day = 0.5**, **Custom Duration = hours ÷ 7.5**.
            - For each school year we sum those values → that is **Total # of Absences** for that year.

            **How to verify the table:**
            - For any row: **Total # of Absences × Replacement Cost Per Day** should equal **Total Replacement Cost to District**.
            - Example: 14,683.79 × $132.30 ≈ $1,942,664.98 ✓
            - **Overall (Cumulative)** = sum across all school years; **5-Yr Avg** = average per year.
            """)
        st.markdown("---")
    
    # ============================================================================
    # CALCULATION BREAKDOWN (For Validation)
    # ============================================================================
    if results.get("cc_range_details") or results.get("high_claimant_details") or results.get("per_school_year_breakdown"):
        st.subheader("🔍 Calculation Breakdown (For Validation)")
        st.caption("Overall numbers below are **cumulative across all school years**. For a **year-by-year** breakdown, see the table under « Calculation Breakdown by School Year ».")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Teacher Distribution (All Years):**")
            st.write(f"- Total Teachers: {results.get('total_teachers', 0):,}")
            st.write(f"- Below Deductible (≤{deductible}): {results.get('below_deductible_count', 0):,}")
            st.write(f"- In CC Range ({deductible+1}-{cc_maximum}): {results.get('num_staff_cc_range', 0):,}")
            st.write(f"- High Claimants (>{cc_maximum}): {results.get('num_high_claimant', 0):,}")
        with col2:
            st.write("**Calculation Summary:**")
            st.write(f"- Deductible: {deductible} days")
            st.write(f"- CC Days: {cc_days} days")
            st.write(f"- CC Maximum: {cc_maximum} days")
            st.write(f"- Replacement Cost: ${replacement_cost:.2f}/day")
        # Per-school-year calculation breakdown (yearly, not cumulative)
        if results.get("per_school_year_breakdown"):
            st.markdown("---")
            st.write("**📅 Calculation Breakdown by School Year**")
            breakdown = results["per_school_year_breakdown"]
            by_year_rows = []
            for sy in sorted(breakdown.keys()):
                b = breakdown[sy]
                by_year_rows.append({
                    "School Year": sy,
                    "Total Teachers": f"{b['total_teachers']:,}",
                    "Below Deductible": f"{b['below_deductible']:,}",
                    "In CC Range": f"{b['in_cc_range']:,}",
                    "High Claimant": f"{b['high_claimant']:,}",
                    "Total CC Days": f"{b['total_cc_days']:,.2f}",
                    "Excess Days": f"{b['excess_days']:,.2f}",
                    "Replacement Cost ($)": f"${b.get('replacement_cost_cc', 0):,.2f}",
                    "Carrier Profit Margin ($)": f"${b.get('ark_commission', 0):,.2f}",
                    "ABCover Acquisition Costs ($)": f"${b.get('abcover_commission', 0):,.2f}",
                    "Premium ($)": f"${b['premium']:,.2f}",
                })
            # Average row (last row)
            n_years = len(breakdown)
            if n_years > 0:
                sum_teachers = sum(b['total_teachers'] for b in breakdown.values())
                sum_below = sum(b['below_deductible'] for b in breakdown.values())
                sum_cc = sum(b['in_cc_range'] for b in breakdown.values())
                sum_high = sum(b['high_claimant'] for b in breakdown.values())
                sum_cc_days = sum(b['total_cc_days'] for b in breakdown.values())
                sum_excess = sum(b['excess_days'] for b in breakdown.values())
                sum_rc = sum(b.get('replacement_cost_cc', 0) for b in breakdown.values())
                sum_ark = sum(b.get('ark_commission', 0) for b in breakdown.values())
                sum_abcover = sum(b.get('abcover_commission', 0) for b in breakdown.values())
                sum_premium = sum(b['premium'] for b in breakdown.values())
                avg_metrics = {
                    'total_teachers': sum_teachers / n_years,
                    'below_deductible': sum_below / n_years,
                    'in_cc_range': sum_cc / n_years,
                    'high_claimant': sum_high / n_years,
                    'total_cc_days': sum_cc_days / n_years,
                    'excess_days': sum_excess / n_years,
                    'replacement_cost_cc': sum_rc / n_years,
                    'ark_commission': sum_ark / n_years,
                    'abcover_commission': sum_abcover / n_years,
                    'premium': sum_premium / n_years,
                }
                by_year_rows.append({
                    "School Year": "5 yr Avg",
                    "Total Teachers": f"{avg_metrics['total_teachers']:,.1f}",
                    "Below Deductible": f"{avg_metrics['below_deductible']:,.1f}",
                    "In CC Range": f"{avg_metrics['in_cc_range']:,.1f}",
                    "High Claimant": f"{avg_metrics['high_claimant']:,.1f}",
                    "Total CC Days": f"{avg_metrics['total_cc_days']:,.2f}",
                    "Excess Days": f"{avg_metrics['excess_days']:,.2f}",
                    "Replacement Cost ($)": f"${avg_metrics['replacement_cost_cc']:,.2f}",
                    "Carrier Profit Margin ($)": f"${avg_metrics['ark_commission']:,.2f}",
                    "ABCover Acquisition Costs ($)": f"${avg_metrics['abcover_commission']:,.2f}",
                    "Premium ($)": f"${avg_metrics['premium']:,.2f}",
                })
            st.dataframe(_dataframe_safe_for_display(pd.DataFrame(by_year_rows)), width="stretch", hide_index=True)
            st.caption("Each row shows metrics for **that school year only** (not cumulative). Last row is **average** across years.")
        if results.get("cc_range_details"):
            with st.expander("📋 CC Range Staff Details (How CC Days are Calculated)", expanded=False):
                cc_details = results["cc_range_details"]
                if len(cc_details) > 0:
                    st.dataframe(_dataframe_safe_for_display(pd.DataFrame(cc_details)), width="stretch", hide_index=True)
                    st.caption(f"Total CC Days: {results.get('total_cc_days', 0):.2f}")
                else:
                    st.write("No staff in CC range.")
        if results.get("high_claimant_details"):
            with st.expander("⚠️ High Claimant Staff Details (How Excess Days are Calculated)", expanded=False):
                hc_details = results["high_claimant_details"]
                if len(hc_details) > 0:
                    st.dataframe(_dataframe_safe_for_display(pd.DataFrame(hc_details)), width="stretch", hide_index=True)
                    st.caption(f"Total Excess Days: {results.get('excess_days', 0):.2f}")
                else:
                    st.write("No high claimant staff.")
        if (results.get("cc_range_details") or results.get("high_claimant_details")):
            st.caption("💡 **If first/last names are blank:** In Step 2, include the columns that contain employee first and last names in \"Select columns to keep\". You can map them to **Employee First Name** / **Employee Last Name** or keep names like **First Name** / **Last Name** — both work.")
        st.markdown("---")
    
    # Coverage Metrics (show average values when we have per-year breakdown)
    st.subheader("📈 Coverage Metrics")
    if avg_metrics is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Staff in CC Range (Avg)", f"{avg_metrics['in_cc_range']:,.1f}")
        with col2:
            st.metric("Total CC Days (Avg)", f"{avg_metrics['total_cc_days']:,.2f}")
        with col3:
            st.metric("Replacement Cost × CC Days (Avg)", f"${avg_metrics['replacement_cost_cc']:,.2f}")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Staff in CC Range", f"{results.get('num_staff_cc_range', 0):,}")
        with col2:
            st.metric("Total CC Days", f"{results.get('total_cc_days', 0):,.2f}")
        with col3:
            st.metric("Replacement Cost × CC Days", f"${results.get('replacement_cost_cc', 0):,.2f}")
    
    # High Claimant Metrics (no reasoning caption)
    st.subheader("⚠️ High Claimant Metrics")
    if avg_metrics is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High Claimant Staff (Avg)", f"{avg_metrics['high_claimant']:,.1f}")
        with col2:
            st.metric("Excess Days (Avg)", f"{avg_metrics['excess_days']:,.2f}")
        with col3:
            high_claimant_cost_avg = (avg_metrics['excess_days'] * replacement_cost) if avg_metrics else 0
            st.metric("High Claimant Cost (Avg)", f"${high_claimant_cost_avg:,.2f}")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High Claimant Staff", f"{results.get('num_high_claimant', 0):,}")
        with col2:
            st.metric("Excess Days", f"{results.get('excess_days', 0):,.2f}")
        with col3:
            st.metric("High Claimant Cost", f"${results.get('high_claimant_cost', 0):,.2f}")
    
    # Premium Calculation (show average values when we have per-year breakdown)
    st.subheader("💰 Premium Calculation")
    if avg_metrics is not None:
        rc_cc = avg_metrics['replacement_cost_cc']
        ark = avg_metrics['ark_commission']
        abcover = avg_metrics['abcover_commission']
        total_premium_val = avg_metrics['premium']
        st.caption("Values below are **averages** from the Calculation Breakdown by School Year table.")
    else:
        rc_cc = results.get("replacement_cost_cc", 0)
        ark = results.get("ark_commission", 0)
        abcover = results.get("abcover_commission", 0)
        total_premium_val = results.get("total_premium", 0)
    st.markdown(f"""
    - **Replacement Cost (CC):** ${rc_cc:,.2f}  
    - **Carrier Profit Margin:** ${ark:,.2f}  
    - **ABCover Acquisition Costs:** ${abcover:,.2f}  
    - **TOTAL PREMIUM:** ${total_premium_val:,.2f}
    """)
    st.success(f"**Total premium:** ${total_premium_val:,.2f}")
    
    # Summary table
    st.subheader("📋 Summary")
    summary_data = {
        'Metric': [
            'Deductible (Days)',
            'CC Days per Teacher',
            'CC Maximum (Deductible + CC)',
            'Replacement Cost per Day',
            'School Year Days'
        ],
        'Value': [
            deductible,
            cc_days,
            cc_maximum,
            f"${replacement_cost:.2f}",
            school_year_days
        ]
    }
    st.dataframe(_dataframe_safe_for_display(pd.DataFrame(summary_data)), width="stretch", hide_index=True)
    
    # Show processing history
    with st.expander("📜 Processing History (Blackboard)", expanded=False):
        history = st.session_state.agent_state.get("processing_history", [])
        for i, step in enumerate(history, 1):
            st.write(f"{i}. {step.get('step', 'Unknown')}: {step.get('status', 'Unknown')}")

# Footer
st.markdown("---")
st.caption("ABCover Multi-Agent System | LangGraph + LLM Agents | Blackboard Pattern")
