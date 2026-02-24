"""
LangGraph Orchestrator - Manages multi-agent workflow with state (blackboard)
Uses LangGraph for state management and agent coordination
"""

import os
from typing import TypedDict, Annotated, Any
from langgraph.graph import StateGraph, END
import pandas as pd
from dotenv import load_dotenv
from .blackboard import Blackboard
from .file_upload_agent import FileUploadAgent
from .data_selection_agent import DataSelectionAgent
from .data_cleaning_agent_llm import DataCleaningAgentLLM
from .rating_engine_agent_llm import RatingEngineAgentLLM

load_dotenv()

# Common date formats in school absence exports (try these first for fast single-pass parse)
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%B %d, %Y",  # July 1, 2020
    "%b %d, %Y",  # Jul 1, 2020
    "%m/%d/%y",
    "%d-%b-%Y",
]


def _parse_date_series_fast(ser: pd.Series) -> pd.Series:
    """
    Parse a series to datetime using explicit formats when possible to avoid
    per-element dateutil fallback (slow on large data). Only use for the real
    absence 'Date' column, not Hire Date or other date columns.
    """
    if ser.empty:
        return pd.to_datetime(ser, errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(ser):
        return ser
    # Try each format; use the one that parses the most non-null values
    best = None
    best_count = -1
    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.to_datetime(ser, format=fmt, errors="coerce")
            count = parsed.notna().sum()
            if count > best_count:
                best_count = count
                best = parsed
        except (ValueError, TypeError):
            continue
    if best is not None and best_count > 0:
        return best
    return pd.to_datetime(ser, errors="coerce")


class AgentState(TypedDict, total=False):
    """
    State managed by LangGraph (like blackboard).
    All agents can read/write to this state.
    """
    # Input
    uploaded_file: Any  # Streamlit UploadedFile
    
    # Data
    raw_data: pd.DataFrame
    selected_data: pd.DataFrame
    cleaned_data: pd.DataFrame
    
    # Analysis and reasoning
    data_analysis: dict
    cleaning_reasoning: dict
    calculation_reasoning: dict
    
    # Results
    rating_results: dict
    
    # Metadata
    school_name: str
    selected_columns: list
    column_map: dict  # optional: { original_column_name: standard_name }
    filters: dict
    rating_inputs: dict
    
    # Processing history
    processing_history: Annotated[list, lambda x, y: x + y]  # Append-only list


class LangGraphOrchestrator:
    """
    Orchestrates agents using LangGraph with state management (blackboard pattern).
    """
    
    def __init__(self):
        """Initialize orchestrator and agents. LLM provider/model from env: LLM_PROVIDER, LLM_MODEL."""
        self.upload_agent = FileUploadAgent()
        self.selection_agent = DataSelectionAgent()
        provider = (os.getenv("LLM_PROVIDER") or "google").strip().lower()
        model_name = (os.getenv("LLM_MODEL") or "").strip() or None
        self.cleaning_agent = DataCleaningAgentLLM(model_provider=provider, model_name=model_name)
        self.rating_agent = RatingEngineAgentLLM(model_provider=provider, model_name=model_name)
        
        # Create graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create graph with state
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("upload", self._upload_node)
        workflow.add_node("select", self._select_node)
        workflow.add_node("clean", self._clean_node)
        workflow.add_node("calculate", self._calculate_node)
        
        # Define flow
        workflow.set_entry_point("upload")
        workflow.add_edge("upload", "select")
        workflow.add_edge("select", "clean")
        workflow.add_edge("clean", "calculate")
        workflow.add_edge("calculate", END)
        
        # Compile graph
        return workflow.compile()
    
    def _upload_node(self, state: AgentState) -> AgentState:
        """Upload file node."""
        uploaded_file = state.get("uploaded_file")
        
        if uploaded_file:
            df, error = self.upload_agent.process(uploaded_file)
            if error:
                raise ValueError(f"Upload error: {error}")
            
            return {
                "raw_data": df,
                "processing_history": [{"step": "upload", "status": "success", "rows": len(df)}]
            }
        return state
    
    def _select_node(self, state: AgentState) -> AgentState:
        """Data selection node. Applies column_map (original -> standard names) and derives School Year from Date if needed."""
        df = state.get("raw_data")
        selected_columns = state.get("selected_columns", [])
        filters = state.get("filters", {})
        column_map = state.get("column_map") or {}
        
        if df is not None:
            # Keep only selected columns
            cols = [c for c in selected_columns if c in df.columns]
            if not cols:
                raise ValueError("No selected columns found in data.")
            df = df[cols].copy()
            # Apply column mapping (rename to standard names; derive School Year only from real "Date" column)
            # Strictly only the absence "Date" column is used for date parsing; not Hire Date or other date columns.
            if column_map:
                rename_map = {}
                for orig, standard in column_map.items():
                    if orig not in df.columns or not standard or standard == "Keep as-is":
                        continue
                    if standard == "School Year":
                        orig_normalized = str(orig).strip().lower()
                        if orig_normalized == "date":
                            # Only derive School Year from the real absence Date column (fast parse)
                            try:
                                dates = _parse_date_series_fast(df[orig])
                                year_start = dates.dt.year.where(dates.dt.month >= 7, dates.dt.year - 1)
                                df["School Year"] = year_start.astype(str) + "-" + (year_start + 1).astype(str)
                                df = df.drop(columns=[orig], errors="ignore")
                            except Exception:
                                rename_map[orig] = standard
                        else:
                            # Other columns mapped to School Year (e.g. already "School Year", or Hire Date): just rename
                            rename_map[orig] = standard
                    else:
                        rename_map[orig] = standard
                df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
            # Deduplicate columns after rename (multiple originals can map to same standard name)
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]
            df_selected, error = self.selection_agent.process(df, df.columns.tolist(), filters)
            if error:
                raise ValueError(f"Selection error: {error}")
            
            return {
                "selected_data": df_selected,
                "processing_history": [{"step": "select", "status": "success", "rows": len(df_selected)}]
            }
        return state
    
    def _clean_node(self, state: AgentState) -> AgentState:
        """Data cleaning node (LLM-powered)."""
        df = state.get("selected_data")
        school_name = state.get("school_name")
        filters = state.get("filters", {})
        
        if df is not None and not df.empty:
            # LLM agent can see full context from state (blackboard)
            # Prepare blackboard context for LLM
            blackboard_context = {
                "has_raw_data": not state.get("raw_data", pd.DataFrame()).empty,
                "has_selected_data": not state.get("selected_data", pd.DataFrame()).empty,
                "raw_data_rows": len(state.get("raw_data", pd.DataFrame())),
                "selected_data_rows": len(state.get("selected_data", pd.DataFrame())),
                # IMPORTANT: Tell cleaning agent if user already filtered Employee Types
                "user_selected_employee_types": filters.get("employee_type", None),
                "user_already_filtered_employee_types": "employee_type" in filters and filters["employee_type"] is not None
            }
            
            df_cleaned, cleaning_stats = self.cleaning_agent.process(df, school_name, blackboard_context)
            
            return {
                "cleaned_data": df_cleaned,
                "cleaning_reasoning": cleaning_stats.get("llm_reasoning"),
                "data_analysis": cleaning_stats.get("suggested_rules", {}),
                "processing_history": [{
                    "step": "clean",
                    "status": "success",
                    "rows": len(df_cleaned),
                    "reasoning": cleaning_stats.get("llm_reasoning", "")
                }]
            }
        return state
    
    # Standard column names required by the rating engine (others may be normalized to these)
    _REQUIRED_CALC_COLUMNS = ['School Year', 'Employee Identifier', 'Absence_Days']
    # Common alternatives (case-insensitive match) -> standard name
    _COLUMN_ALIASES = {
        'school year': 'School Year',
        'schoolyear': 'School Year',
        'sy': 'School Year',
        'fiscal year': 'School Year',
        'date': 'Date',
        'absence date': 'Date',
        'absent date': 'Date',
        'day': 'Date',
        'date of absence': 'Date',
        'employee identifier': 'Employee Identifier',
        'employee id': 'Employee Identifier',
        'emp id': 'Employee Identifier',
        'employee_id': 'Employee Identifier',
        'employee first name': 'Employee First Name',
        'employee first': 'Employee First Name',
        'first name': 'Employee First Name',
        'first_name': 'Employee First Name',
        'firstname': 'Employee First Name',
        'given name': 'Employee First Name',
        'given': 'Employee First Name',
        'employee last name': 'Employee Last Name',
        'employee last': 'Employee Last Name',
        'last name': 'Employee Last Name',
        'last_name': 'Employee Last Name',
        'lastname': 'Employee Last Name',
        'surname': 'Employee Last Name',
        'family name': 'Employee Last Name',
        'absence_days': 'Absence_Days',
        'absence days': 'Absence_Days',
        'total_days': 'Absence_Days',
        'days': 'Absence_Days',
        'percent of day': 'Absence_Days',  # Percent of Day is already in days
        'absence': 'Absence_Days',
    }

    def _normalize_calc_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to standard names if they match known aliases. Returns a copy."""
        if df is None or df.empty:
            return df
        col_map = {}
        for c in df.columns:
            c_str = str(c).strip()
            target = None
            if c_str.lower() in self._COLUMN_ALIASES:
                target = self._COLUMN_ALIASES[c_str.lower()]
            else:
                key_no_space = c_str.lower().replace(' ', '')
                if key_no_space in self._COLUMN_ALIASES:
                    target = self._COLUMN_ALIASES[key_no_space]
            # IMPORTANT: Do NOT map Duration -> Absence_Days when Absence_Days already exists.
            # Duration is HOURS (e.g. 7.5); Absence_Days from cleaning is correct DAYS (1.0, 0.5).
            if target == 'Absence_Days' and 'Absence_Days' in df.columns and c_str.lower() in ('duration',):
                continue  # Skip - would wrongly add hours as days
            if target:
                col_map[c] = target
        if col_map:
            df = df.rename(columns=col_map)
        return df

    @staticmethod
    def _derive_school_year_from_date(df: pd.DataFrame) -> pd.DataFrame:
        """If 'School Year' is missing but 'Date' exists, derive School Year (July 1 - June 30). Uses fast date parse (Date = absence date only)."""
        if df is None or df.empty or 'School Year' in df.columns:
            return df
        if 'Date' not in df.columns:
            return df
        try:
            dates = _parse_date_series_fast(df['Date'])
            # July 1+ -> current year start; before July -> previous year start
            year_start = dates.dt.year.where(dates.dt.month >= 7, dates.dt.year - 1)
            year_end = year_start + 1
            df = df.copy()
            df['School Year'] = year_start.astype(str) + '-' + year_end.astype(str)
        except Exception:
            pass
        return df

    def _calculate_node(self, state: AgentState) -> AgentState:
        """Rating engine calculation node (LLM-powered)."""
        df = state.get("cleaned_data")
        rating_inputs = state.get("rating_inputs", {})
        school_name = state.get("school_name")
        
        if df is not None and not df.empty and rating_inputs:
            # Normalize column names so 'School Year', 'Employee Identifier', 'Absence_Days' exist
            df = self._normalize_calc_columns(df.copy())
            # If still no School Year but we have Date, derive it (July 1 - June 30)
            df = self._derive_school_year_from_date(df)
            missing = [c for c in self._REQUIRED_CALC_COLUMNS if c not in df.columns]
            if missing:
                available = list(df.columns)
                need_date = 'School Year' in missing
                hint = (
                    "You need a column for **absence date** or **school year**. "
                    "In Step 2, include the column that has the date of each absence (e.g. 'Date', 'Absence Date', 'Day') and map it to **Date**, or include a 'School Year' column. "
                    "We derive School Year from Date (July 1–June 30) when Date is provided."
                ) if need_date else (
                    "In Step 2, ensure you keep the columns that contain School Year (or Date), Employee ID, and Absence/Duration days, and map them to standard names (e.g. 'School Year' or 'Date', 'Employee Identifier', 'Absence_Days')."
                )
                raise KeyError(
                    f"Cleaned data is missing columns required for the rating calculation: {missing}. "
                    f"Your data has columns: {available}. {hint}"
                )
            # Keep full cleaned data for rating (so first/last name and other columns are available for detail tables)
            cleaned_data_full = df.copy()
            # Handle duplicate columns (multiple cols can map to same standard name)
            # Build a clean 3-column df for teacher_days aggregation only
            def _single_col(d, name, combine_sum=False):
                cols = [i for i, c in enumerate(d.columns) if c == name]
                if not cols:
                    return None
                if combine_sum and len(cols) > 1:
                    return d.iloc[:, cols].sum(axis=1)
                return d.iloc[:, cols[0]]
            df_calc = pd.DataFrame({
                'School Year': _single_col(df, 'School Year'),
                'Employee Identifier': _single_col(df, 'Employee Identifier'),
                'Absence_Days': _single_col(df, 'Absence_Days', combine_sum=True),
            })
            # Calculate teacher absence days first
            teacher_days = df_calc.groupby(['School Year', 'Employee Identifier'])['Absence_Days'].sum().reset_index()
            # Only assign names if count matches (avoids length mismatch with duplicate cols)
            if len(teacher_days.columns) == 3:
                teacher_days.columns = ['School Year', 'Employee Identifier', 'Total_Days']
            
            # Get rating inputs
            deductible = rating_inputs.get("deductible", 20)
            cc_days = rating_inputs.get("cc_days", 60)
            replacement_cost = rating_inputs.get("replacement_cost", 150.0)
            ark_commission = rating_inputs.get("ark_commission_rate", 0.15)
            abcover_commission = rating_inputs.get("abcover_commission_rate", 0.15)
            school_year_days = rating_inputs.get("school_year_days", 180)
            
            # LLM agent can see full context from state (blackboard)
            # Prepare blackboard context for LLM
            blackboard_context = {
                "has_raw_data": not state.get("raw_data", pd.DataFrame()).empty,
                "has_selected_data": not state.get("selected_data", pd.DataFrame()).empty,
                "has_cleaned_data": not state.get("cleaned_data", pd.DataFrame()).empty,
                "cleaning_reasoning": state.get("cleaning_reasoning", ""),
                "raw_data_rows": len(state.get("raw_data", pd.DataFrame())),
                "selected_data_rows": len(state.get("selected_data", pd.DataFrame())),
                "cleaned_data_rows": len(state.get("cleaned_data", pd.DataFrame())),
            }
            
            # Calculate with LLM reasoning (with full blackboard context)
            # Pass teacher_days (aggregated) and full cleaned_data (so CC/High Claimant tables get first/last name)
            results, reasoning = self.rating_agent.process(
                teacher_days,
                cleaned_data_full,  # Full DataFrame: staff/absences per year + first/last name for detail tables
                deductible,
                cc_days,
                replacement_cost,
                ark_commission,
                abcover_commission,
                school_name,
                blackboard_context,
                school_year_days  # Pass school year days for reference
            )
            
            return {
                "rating_results": results,
                "calculation_reasoning": reasoning,
                "processing_history": [{
                    "step": "calculate",
                    "status": "success",
                    "premium": results.get("total_premium", 0)
                }]
            }
        return state
    
    def run(self, uploaded_file, selected_columns=None, filters=None, 
            school_name=None, rating_inputs=None) -> AgentState:
        """
        Run the complete workflow.
        
        Args:
            uploaded_file: File to upload
            selected_columns: Columns to select
            filters: Row filters
            school_name: School name
            rating_inputs: Rating engine inputs
            
        Returns:
            Final state with all results
        """
        # Initial state
        initial_state: AgentState = {
            "uploaded_file": uploaded_file,
            "selected_columns": selected_columns or [],
            "filters": filters or {},
            "school_name": school_name or "",
            "rating_inputs": rating_inputs or {},
            "raw_data": pd.DataFrame(),
            "selected_data": pd.DataFrame(),
            "cleaned_data": pd.DataFrame(),
            "data_analysis": {},
            "cleaning_reasoning": {},
            "calculation_reasoning": {},
            "rating_results": {},
            "processing_history": []
        }
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        return final_state
