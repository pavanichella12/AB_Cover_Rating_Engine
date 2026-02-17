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
        # Prepare summary for LLM
        cols = df.columns.tolist()
        sample = df.head(5).to_dict("records") if len(df) > 0 else []
        sample_str = json.dumps(sample, indent=2, default=str)
        standard_str = json.dumps(standard_columns)
        prompt = f"""You analyze school absence data files. Different schools use different column names.
Our company uses these STANDARD column names: {standard_str}

This school's data has columns: {cols}

Sample data (first 5 rows):
{sample_str}

For each school column, decide which standard name it maps to (if any). Use the column name AND sample values to infer meaning.
- "Employee Identifier" / "Employee ID" = unique staff ID (e.g. AEnglish, 12345)
- "School Year" = fiscal year like "2020-2021", OR a date column we can derive it from
- "Absence_Days" = ONLY map "Percent of Day" or columns that are ALREADY in days (0.5, 1.0). DO NOT map "Duration" - Duration is typically HOURS (e.g. 7.5). Our system calculates Absence_Days from Absence Type + Duration.
- "Date" = absence date (when the absence occurred). DO NOT map "Hire Date" to "Date" - Hire Date is when the employee was hired, not the absence date. Do not map Hire Date to any standard column; leave it unmapped or exclude it.
- "School Name", "Reason", "Employee Title", "Employee Type", "Absence Type", etc.
- Keep "Duration" and "Absence Type" as-is - our cleaning agent uses them to compute Absence_Days.

If a school column doesn't match any standard, DO NOT include it in the mapping (we keep it as-is).

Respond with ONLY a JSON object, no other text. Example: {{"Emp ID": "Employee Identifier", "Percent of Day": "Absence_Days"}} - do NOT map Duration to Absence_Days.
Use the EXACT school column names as keys and EXACT standard names as values. Map "Date" to "School Year" if there is no School Year column (we derive it from dates).
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
