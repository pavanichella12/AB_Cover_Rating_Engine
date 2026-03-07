"""
DataAnalysisAgent - LLM-powered agent that analyzes school data
Responsibility: Understand data structure, identify patterns, suggest cleaning rules
"""

import pandas as pd
from typing import Dict, Any, Optional, Tuple
from .llm_agent_base import LLMAgentBase
import json


class DataAnalysisAgent(LLMAgentBase):
    """
    LLM-powered agent that analyzes uploaded school data.
    
    Tasks:
    - Understand data structure and columns
    - Identify data quality issues
    - Suggest appropriate cleaning rules
    - Reason about school-specific patterns
    """
    
    def __init__(self, model_provider: str = "google", model_name: Optional[str] = None):
        super().__init__("DataAnalysisAgent", model_provider, model_name)
    
    def _get_system_prompt(self) -> str:
        return """You are a data analysis expert specializing in school absence data.
Your role is to:
1. Analyze uploaded school absence data files
2. Understand the data structure, columns, and patterns
3. Identify data quality issues (missing values, inconsistencies, outliers)
4. Suggest appropriate cleaning rules based on the specific school's data patterns
5. Reason about school-specific characteristics (e.g., different absence types, employee categories)

When analyzing data:
- Look for patterns that might be school-specific
- Consider edge cases and unusual data points
- Provide clear, actionable recommendations
- Explain your reasoning for suggested cleaning rules

Always respond in JSON format with:
{
    "data_summary": {...},
    "quality_issues": [...],
    "suggested_rules": [...],
    "reasoning": "..."
}
"""
    
    def analyze_data_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze the structure of the uploaded data.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Prepare data summary for LLM
        data_summary = {
            "rows": len(df),
            "columns": df.columns.tolist(),
            "data_types": df.dtypes.astype(str).to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "sample_rows": df.head(3).to_dict('records') if len(df) > 0 else []
        }
        
        # Create prompt for LLM
        prompt = f"""Analyze this school absence data:

Data Summary:
- Total Rows: {data_summary['rows']}
- Columns: {', '.join(data_summary['columns'])}
- Data Types: {json.dumps(data_summary['data_types'], indent=2)}
- Missing Values: {json.dumps(data_summary['missing_values'], indent=2)}

Sample Data (first 3 rows):
{json.dumps(data_summary['sample_rows'], indent=2, default=str)}

Please analyze:
1. What is the structure and purpose of each column?
2. Are there any data quality issues?
3. What cleaning rules would be appropriate for this school's data?
4. Are there any school-specific patterns or characteristics?

Respond in JSON format."""
        
        # Get LLM analysis
        llm_response = self._call_llm(prompt)
        
        # Try to parse JSON response
        try:
            analysis = json.loads(llm_response)
        except json.JSONDecodeError:
            # If LLM doesn't return JSON, create structured response
            analysis = {
                "data_summary": data_summary,
                "quality_issues": [],
                "suggested_rules": [],
                "reasoning": llm_response
            }
        
        return analysis
    
    def suggest_cleaning_rules(self, df: pd.DataFrame, school_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Suggest cleaning rules based on data analysis.
        
        Args:
            df: DataFrame to analyze
            school_name: Optional school name for context
            
        Returns:
            Dictionary with suggested cleaning rules and reasoning
        """
        # Analyze data first
        analysis = self.analyze_data_structure(df)
        
        # Create prompt for rule suggestions
        prompt = f"""Based on this school absence data analysis:

{json.dumps(analysis, indent=2, default=str)}

School Name: {school_name or 'Unknown'}

Please suggest specific cleaning rules for this school's data. Consider:
1. Which records should be filtered out? (e.g., Unfilled + NO Substitute)
2. Which employee types should be included? (e.g., Teachers only)
3. How should absence days be calculated?
4. Are there school-specific rules or patterns?

Provide your suggestions in JSON format:
{{
    "filter_rules": [
        {{"rule": "description", "reasoning": "why", "implementation": "code snippet"}}
    ],
    "calculation_rules": [
        {{"rule": "description", "reasoning": "why", "implementation": "code snippet"}}
    ],
    "school_specific_notes": "..."
}}
"""
        
        llm_response = self._call_llm(prompt)
        
        try:
            suggestions = json.loads(llm_response)
        except json.JSONDecodeError:
            suggestions = {
                "filter_rules": [],
                "calculation_rules": [],
                "school_specific_notes": llm_response
            }
        
        return suggestions
    
    def suggest_column_mapping(
        self, df: pd.DataFrame, standard_columns: list
    ) -> Dict[str, str]:
        """
        Analyze the data and suggest mapping from school column names to standard names.
        Columns that don't match any standard are not included (keep as-is).
        
        Args:
            df: Raw DataFrame from uploaded file
            standard_columns: List of our company's standard column names
            
        Returns:
            Dict mapping {school_column_name: standard_name}. Unmapped columns omitted.
        """
        if df is None or df.empty:
            return {}
        # Prepare summary for LLM: column names, sample rows, AND per-column value view so AI can "see" the data
        cols = df.columns.tolist()
        sample = df.head(5).to_dict("records") if len(df) > 0 else []
        sample_str = json.dumps(sample, indent=2, default=str)
        standard_str = json.dumps(standard_columns)

        def _column_value_summary(series, max_categories=12):
            """What we see in this column: dtype + value distribution so AI can infer meaning."""
            if series is None or series.empty:
                return {"dtype": "empty", "values": []}
            dtype = str(series.dtype)
            # For object/category: show value_counts (top values). For numeric: show sample + min/max if useful.
            if pd.api.types.is_numeric_dtype(series):
                dropna = series.dropna()
                if len(dropna) == 0:
                    return {"dtype": dtype, "values": []}
                uniq = dropna.unique()
                if len(uniq) <= max_categories:
                    sample_vals = sorted(uniq.tolist())[:max_categories]
                else:
                    sample_vals = [float(series.min()), float(series.max()), "… (numeric)"]
                return {"dtype": dtype, "values": sample_vals}
            vc = series.dropna().astype(str).value_counts()
            top = vc.head(max_categories)
            return {"dtype": dtype, "values": list(top.to_dict().keys())}

        column_value_view = {}
        for c in cols:
            try:
                column_value_view[c] = _column_value_summary(df[c])
            except Exception:
                column_value_view[c] = {"dtype": "unknown", "values": []}
        column_view_str = json.dumps(column_value_view, indent=2, default=str)

        prompt = f"""You analyze school absence data files. Different schools use different column names.
Our company uses these STANDARD column names: {standard_str}

This school's data has columns: {cols}

**What we SEE in each column (use this to infer meaning — look at actual values):**
{column_view_str}

Sample data (first 5 rows):
{sample_str}

**Instructions — think step by step from the data:**
1. Look at each column's NAME and its VALUES above. Infer meaning from both.
2. Numeric column with values like 0.5, 1, 2, 1.0 → likely days (map to "Absence_Days" if it clearly is days). Numeric column with 7.5, 3.5, 6 → likely HOURS (keep as "Duration", do NOT map to Absence_Days).
3. Column with values like Sick, Personal, Vacation, Professional Development → reason for leave (map to "Reason" or keep as "Absence Type"; our logic uses Absence Type for duration only when it says Full Day/Half Day, so reason-of-leave columns are fine as Absence Type or Reason).
4. Column with values like Teacher, Aide, Substitute → job category → "Employee Type". Column with values like 2020-2021, 2021-2022 → "School Year". Column with date-like values → "Date" (absence date; NOT Hire Date).
5. "Employee Identifier" = unique staff ID. "Employee First Name" / "Employee Last Name" = names for reports.
6. Map "Date" to "School Year" only if there is no dedicated School Year column (we derive year from dates). Do NOT map Hire Date to Date or School Year.

For each school column, decide which standard name it maps to (if any). If a column doesn't match any standard, omit it from the mapping.
Respond with ONLY a JSON object, no other text. Example: {{"Emp ID": "Employee Identifier", "Days of Absence": "Absence_Days"}}.
Use EXACT school column names as keys and EXACT standard names as values.
"""
        try:
            response = self._call_llm(prompt)
            # Extract JSON (handle markdown code blocks)
            text = response.strip()
            if "```" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    text = text[start:end]
            mapping = json.loads(text)
            if not isinstance(mapping, dict):
                return {}
            # Validate: keys must exist in df, values must be in standard_columns
            result = {}
            for k, v in mapping.items():
                if k in df.columns and v in standard_columns:
                    result[str(k)] = str(v)
            return result
        except Exception:
            return {}

    def process(self, df: pd.DataFrame, school_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete analysis process.
        
        Args:
            df: DataFrame to analyze
            school_name: Optional school name
            
        Returns:
            Complete analysis with structure, quality issues, and suggestions
        """
        analysis = self.analyze_data_structure(df)
        suggestions = self.suggest_cleaning_rules(df, school_name)
        
        return {
            "analysis": analysis,
            "suggestions": suggestions,
            "school_name": school_name
        }
