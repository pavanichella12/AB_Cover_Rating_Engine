"""
DataCleaningAgentLLM - LLM-powered agent for data cleaning
Responsibility: Reason about cleaning rules, adapt to school-specific patterns
"""

import pandas as pd
from typing import Dict, Any, Optional, Tuple
from .llm_agent_base import LLMAgentBase
import json


class DataCleaningAgentLLM(LLMAgentBase):
    """
    LLM-powered agent for data cleaning.
    
    Tasks:
    - Analyze data patterns and reason about cleaning needs
    - Suggest appropriate cleaning rules based on school-specific patterns
    - Adapt rules to different schools
    - Apply cleaning rules (deterministic execution)
    """
    
    def __init__(self, model_provider: str = "google", model_name: Optional[str] = None):
        super().__init__("DataCleaningAgentLLM", model_provider, model_name)
    
    def _get_system_prompt(self) -> str:
        return """You are a data cleaning expert specializing in school absence data analysis for ABCover's Rating Engine.

YOUR EXPERTISE (Based on extensive EDA analysis of multiple schools):
You have analyzed school absence data for multiple districts (Millburn, Butler, Toms River, Woodbridge, Elbert) and understand the patterns.

DATA VALIDATION (Do this FIRST - before business rules):
- Validate data format and structure
- Check required columns exist
- Validate data types (Date should be datetime, Duration should be numeric, etc.)
- Check for completely empty rows
- Validate date formats are parseable
- Check for invalid values (e.g., negative durations, future dates beyond reasonable range)
- Identify format inconsistencies

STANDARD CLEANING RULES (Apply after validation):
1. Rule 1 - Remove Unfilled + NO Substitute:
   - Remove records where Filled='Unfilled' AND Needs Substitute='NO'
   - REASON: These absences don't need substitute coverage, so they're not relevant for insurance calculations
   - KEEP: Records where Filled='Unfilled' BUT Needs Substitute='YES' (they need coverage)
   - KEEP: All records where Filled='Filled' (substitute was provided)

2. Rule 2 - Employee Type Filter:
   - IMPORTANT: If the user (manager/authority) already selected Employee Types in Step 2, RESPECT their selection
   - User selection takes priority because business users know their organization best
   - If user already filtered: DO NOT filter again, just acknowledge and validate their selection
   - If user did NOT filter: Then apply standard rule - Keep only ['Teacher', 'Teacher Music', 'Teacher SpecEd']
   - REASON: These are teaching positions that require substitute coverage
   - ADAPT: Some schools may have additional teacher types (e.g., 'Teacher Aide', 'Teacher Assistant')
   - ANALYZE: Check if school has unusual employee types that should be included (only if user didn't already select)

3. Rule 3 - School Year Date Validation:
   - School years follow July 1 – June 30 calendar
   - Example: School Year "2020-2021" = July 1, 2020 to June 30, 2021
   - Example: School Year "2021-2022" = July 1, 2021 to June 30, 2022
   - VALIDATE: Date must fall within the School Year range
   - REMOVE: Records where Date doesn't match the School Year (e.g., dates in wrong year range)
   - REASON: Ensure data accuracy - dates must align with their assigned School Year

ABSENCE DAYS CALCULATION (Standard formula):
- Full Day = 1.0 day
- AM Half Day = 0.5 day
- PM Half Day = 0.5 day
- Custom Duration = hours / 7.5 (converts hours to days, assuming 7.5 hour workday)
- Other types = 0 days

DATA STRUCTURE YOU'LL SEE:
- Columns: School Year, Date, Reason, Employee Identifier, Hire Date, Employee Title, Employee Type, Start Time, End Time, Duration, Absence Type, Filled, Needs Substitute
- Typical absence types: Full Day (most common ~87%), PM Half Day (~7%), AM Half Day (~5%), Custom Duration (~1%)
- Data spans multiple school years (typically 2020-2021 to 2024-2025)

YOUR TASK:
1. Analyze THIS school's data patterns
2. Compare to standard patterns you know
3. Identify school-specific differences
4. Reason about appropriate cleaning rules
5. Explain WHY each rule makes sense for THIS school

ADAPTATION GUIDELINES:
- If school has standard patterns → Use standard rules
- If school has unusual employee types → Reason about whether to include them
- If school has different absence type formats → Adapt calculation
- If school has data quality issues → Suggest handling strategies

Always provide clear reasoning based on the actual data patterns you observe.
Respond in JSON format with your analysis and suggested rules."""
    
    def reason_about_cleaning_rules(self, df: pd.DataFrame, school_name: Optional[str] = None, blackboard_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Use LLM to reason about appropriate cleaning rules.
        
        Args:
            df: DataFrame to analyze
            school_name: Optional school name for context
            
        Returns:
            Dictionary with reasoning and suggested rules
        """
        # Prepare data summary for LLM
        data_summary = {
            "rows": len(df),
            "columns": df.columns.tolist(),
            "sample_data": df.head(5).to_dict('records') if len(df) > 0 else [],
            "employee_types": df['Employee Type'].value_counts().to_dict() if 'Employee Type' in df.columns else {},
            "filled_status": df['Filled'].value_counts().to_dict() if 'Filled' in df.columns else {},
            "absence_types": df['Absence Type'].value_counts().to_dict() if 'Absence Type' in df.columns else {},
            "missing_values": df.isnull().sum().to_dict(),
        }
        
        # Add school year and date information for Rule 3 validation
        if 'School Year' in df.columns and 'Date' in df.columns:
            school_years = df['School Year'].value_counts().to_dict()
            data_summary["school_years"] = school_years
            data_summary["date_range"] = {
                "min": str(df['Date'].min()) if not df['Date'].isna().all() else None,
                "max": str(df['Date'].max()) if not df['Date'].isna().all() else None
            }
            
            # Check for potential date mismatches (sample check)
            date_mismatches = []
            sample_size = min(100, len(df))  # Check sample for performance
            for idx, row in df.head(sample_size).iterrows():
                school_year = row.get('School Year')
                date = row.get('Date')
                if pd.notna(school_year) and pd.notna(date):
                    try:
                        parts = str(school_year).split('-')
                        if len(parts) == 2:
                            start_year = int(parts[0])
                            end_year = int(parts[1])
                            start_date = pd.Timestamp(year=start_year, month=7, day=1)
                            end_date = pd.Timestamp(year=end_year, month=6, day=30)
                            date_ts = pd.to_datetime(date)
                            if not (start_date <= date_ts <= end_date):
                                date_mismatches.append(f"School Year {school_year} has date {date}")
                    except:
                        pass
            
            if date_mismatches:
                data_summary["date_validation_issues"] = date_mismatches[:10]  # Limit to 10 examples
        
        # Add blackboard context if available
        context_info = ""
        user_already_filtered = False
        user_selected_types = None
        
        if blackboard_context:
            user_already_filtered = blackboard_context.get('user_already_filtered_employee_types', False)
            user_selected_types = blackboard_context.get('user_selected_employee_types', None)
            
            context_info = f"""
BLACKBOARD CONTEXT (Full workflow history):
- Raw Data Available: {blackboard_context.get('has_raw_data', False)}
- Selected Data Available: {blackboard_context.get('has_selected_data', False)}
- User Already Filtered Employee Types: {user_already_filtered}
- User Selected Employee Types: {user_selected_types if user_selected_types else 'None (user did not filter)'}
- IMPORTANT: If user already filtered Employee Types, RESPECT their selection. Do not filter again.
"""
        
        prompt = f"""Analyze this school absence data and reason about appropriate cleaning rules:

School: {school_name or 'Unknown'}
{context_info}
Data Summary:
- Total Rows: {data_summary['rows']:,}
- Columns: {', '.join(data_summary['columns'])}
- Employee Types: {json.dumps(data_summary['employee_types'], indent=2)}
- Filled Status: {json.dumps(data_summary['filled_status'], indent=2)}
- Absence Types: {json.dumps(data_summary['absence_types'], indent=2)}
- Missing Values: {json.dumps(data_summary['missing_values'], indent=2)}
- School Years: {json.dumps(data_summary.get('school_years', {}), indent=2)}
- Date Range: {json.dumps(data_summary.get('date_range', {}), indent=2)}
{f"- Date Validation Issues Found: {json.dumps(data_summary.get('date_validation_issues', []), indent=2)}" if data_summary.get('date_validation_issues') else ""}

Sample Data (first 5 rows):
{json.dumps(data_summary['sample_data'], indent=2, default=str)}

Please reason about:
1. DATA FORMAT VALIDATION (Check first):
   - Are all required columns present? (Date, School Year, Employee Identifier, Absence Type)
   - Are data types correct? (Date is datetime, Duration is numeric, etc.)
   - Are there format issues? (Invalid dates, negative durations, malformed School Year, etc.)
   - Are there completely empty rows that should be removed?
   - Report any data format/validation issues found
2. What cleaning rules are appropriate for this school's data?
3. Should we remove Unfilled + NO Substitute records? Why or why not?
4. Employee Types:
   - If user already selected Employee Types: Acknowledge their selection and validate it's appropriate
   - If user did NOT select: Suggest which employee types should be included (standard: Teacher, Teacher Music, Teacher SpecEd)
   - Are there school-specific types that should be considered?
5. School Year Date Validation:
   - Check if dates match their School Year (July 1 - June 30 calendar)
   - Example: School Year "2020-2021" should have dates from July 1, 2020 to June 30, 2021
   - Identify any records where Date doesn't match the School Year range
   - Should we remove mismatched records?
6. Are there any other data quality issues that need special handling?
7. How should absence days be calculated for this school?

Provide your reasoning and suggested rules in JSON format:
{{
    "reasoning": "Your detailed reasoning about the data and cleaning needs",
    "suggested_rules": {{
        "remove_unfilled_no_substitute": true/false,
        "reason_unfilled": "explanation",
        "employee_types_to_keep": ["list", "of", "types"] (only suggest if user didn't already filter),
        "reason_employee_types": "explanation (acknowledge user selection if they already filtered)",
        "user_selection_respected": true/false (true if user already filtered),
        "validate_school_year_dates": true/false (should we validate dates match School Year?),
        "school_year_date_issues": ["list", "of", "issues", "found"],
        "handle_missing_values": "strategy",
        "absence_days_calculation": "approach",
        "school_specific_notes": "any special considerations"
    }},
    "data_quality_issues": ["list", "of", "issues", "found"]
}}
"""
        
        llm_response = self._call_llm(prompt)
        
        try:
            reasoning = json.loads(llm_response)
        except json.JSONDecodeError:
            # If LLM doesn't return JSON, create default rules
            reasoning = {
                "reasoning": llm_response,
                "suggested_rules": {
                    "remove_unfilled_no_substitute": True,
                    "reason_unfilled": "Default rule: Remove records not needing substitutes",
                    "employee_types_to_keep": ["Teacher", "Teacher Music", "Teacher SpecEd"],
                    "reason_employee_types": "Default: Keep teacher types only",
                    "handle_missing_values": "Keep records, handle in calculations",
                    "absence_days_calculation": "Standard calculation",
                    "school_specific_notes": ""
                },
                "data_quality_issues": []
            }
        
        return reasoning
    
    def validate_data_format(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Validate data format and structure BEFORE applying business rules.
        
        Checks:
        - Required columns exist
        - Data types are correct
        - Date formats are valid
        - No completely empty rows
        - Invalid values (negative durations, etc.)
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Tuple of (validated DataFrame, validation_report)
        """
        df = df.copy()
        validation_report = {
            'format_issues': [],
            'rows_removed': 0,
            'columns_checked': [],
            'data_type_issues': [],
            'invalid_values': []
        }
        
        original_rows = len(df)
        
        # Check required columns
        required_columns = ['Date', 'School Year', 'Employee Identifier', 'Absence Type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            validation_report['format_issues'].append(f"Missing required columns: {missing_columns}")
        
        # Remove completely empty rows (all NaN)
        if not df.empty:
            df = df.dropna(how='all')
            validation_report['rows_removed'] += original_rows - len(df)
            if original_rows != len(df):
                validation_report['format_issues'].append(f"Removed {original_rows - len(df)} completely empty rows")
        
        # Validate Date column format
        if 'Date' in df.columns:
            validation_report['columns_checked'].append('Date')
            try:
                # Try to convert to datetime
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                invalid_dates = df['Date'].isna().sum()
                if invalid_dates > 0:
                    validation_report['data_type_issues'].append(f"Date: {invalid_dates} invalid date values")
                    # Remove rows with invalid dates
                    df = df[df['Date'].notna()]
                    validation_report['rows_removed'] += invalid_dates
            except Exception as e:
                validation_report['format_issues'].append(f"Date column format error: {str(e)}")
        
        # Validate Duration column (should be numeric)
        if 'Duration' in df.columns:
            validation_report['columns_checked'].append('Duration')
            try:
                df['Duration'] = pd.to_numeric(df['Duration'], errors='coerce')
                # Check for negative durations (invalid)
                negative_durations = (df['Duration'] < 0).sum()
                if negative_durations > 0:
                    validation_report['invalid_values'].append(f"Duration: {negative_durations} negative values found")
            except Exception as e:
                validation_report['format_issues'].append(f"Duration column format error: {str(e)}")
        
        # Validate School Year format (should be "YYYY-YYYY")
        if 'School Year' in df.columns:
            validation_report['columns_checked'].append('School Year')
            invalid_school_years = 0
            for idx, row in df.iterrows():
                school_year = str(row.get('School Year', ''))
                if pd.notna(row.get('School Year')):
                    # Check format: should be "YYYY-YYYY"
                    if not (len(school_year) == 9 and school_year[4] == '-'):
                        invalid_school_years += 1
            if invalid_school_years > 0:
                validation_report['format_issues'].append(f"School Year: {invalid_school_years} records with invalid format")
        
        # Validate Employee Identifier (report but do not drop - match EDA/test_toms_river which keeps rows for consistent row counts)
        if 'Employee Identifier' in df.columns:
            validation_report['columns_checked'].append('Employee Identifier')
            empty_identifiers = df['Employee Identifier'].isna().sum()
            if empty_identifiers > 0:
                validation_report['format_issues'].append(f"Employee Identifier: {empty_identifiers} missing values (kept for EDA parity)")
        
        validation_report['final_rows'] = len(df)
        validation_report['rows_removed'] = original_rows - len(df)
        
        return df, validation_report
    
    def apply_rule1(self, df: pd.DataFrame, should_apply: bool = True) -> pd.DataFrame:
        """
        Rule 1: Remove records where Filled='Unfilled' AND Needs Substitute='NO'
        
        Args:
            df: DataFrame to clean
            should_apply: Whether to apply this rule (from LLM reasoning)
            
        Returns:
            Cleaned DataFrame
        """
        if not should_apply:
            return df.copy()
        
        if 'Filled' in df.columns and 'Needs Substitute' in df.columns:
            mask = ~((df['Filled'] == 'Unfilled') & (df['Needs Substitute'] == 'NO'))
            return df[mask].copy()
        return df.copy()
    
    def apply_rule2(self, df: pd.DataFrame, employee_types_to_keep: list) -> pd.DataFrame:
        """
        Rule 2: Keep only specified employee types
        
        Args:
            df: DataFrame to clean
            employee_types_to_keep: List of employee types to keep (from LLM reasoning)
            
        Returns:
            Cleaned DataFrame
        """
        if 'Employee Type' in df.columns and employee_types_to_keep:
            return df[df['Employee Type'].isin(employee_types_to_keep)].copy()
        return df.copy()
    
    def apply_rule3(self, df: pd.DataFrame, should_apply: bool = True) -> pd.DataFrame:
        """
        Rule 3: Validate that dates match their School Year (July 1 - June 30 calendar).
        
        School Year format: "YYYY-YYYY" (e.g., "2020-2021")
        Date range: July 1, YYYY to June 30, YYYY+1
        
        Args:
            df: DataFrame to clean
            should_apply: Whether to apply this rule (from LLM reasoning)
            
        Returns:
            Cleaned DataFrame with mismatched records removed
        """
        if not should_apply:
            return df.copy()
        
        if 'School Year' not in df.columns or 'Date' not in df.columns:
            return df.copy()
        
        df = df.copy()
        
        def get_school_year_range(school_year_str):
            """
            Parse School Year string and return (start_date, end_date).
            Example: "2020-2021" -> (July 1, 2020, June 30, 2021)
            """
            try:
                # Parse "YYYY-YYYY" format
                parts = str(school_year_str).split('-')
                if len(parts) == 2:
                    start_year = int(parts[0])
                    end_year = int(parts[1])
                    # School year: July 1, start_year to June 30, end_year
                    start_date = pd.Timestamp(year=start_year, month=7, day=1)
                    end_date = pd.Timestamp(year=end_year, month=6, day=30)
                    return start_date, end_date
            except (ValueError, AttributeError):
                pass
            return None, None
        
        # Create mask for valid dates
        valid_mask = pd.Series([True] * len(df), index=df.index)
        
        for idx, row in df.iterrows():
            school_year = row.get('School Year')
            date = row.get('Date')
            
            if pd.isna(school_year) or pd.isna(date):
                continue  # Skip if missing data
            
            # Get school year date range
            start_date, end_date = get_school_year_range(school_year)
            
            if start_date is None or end_date is None:
                continue  # Skip if can't parse school year
            
            # Convert date to Timestamp if needed
            if not isinstance(date, pd.Timestamp):
                try:
                    date = pd.to_datetime(date)
                except:
                    valid_mask[idx] = False
                    continue
            
            # Check if date falls within school year range
            if not (start_date <= date <= end_date):
                valid_mask[idx] = False
        
        return df[valid_mask].copy()
    
    def calculate_absence_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate absence days based on Absence Type.
        (This stays deterministic - it's math, not reasoning)
        
        Args:
            df: DataFrame with Absence Type column
            
        Returns:
            DataFrame with 'Absence_Days' column added
        """
        df = df.copy()
        
        # Always recalculate when Absence Type exists - pre-existing Absence_Days may be wrong
        # (e.g. mapped from Duration which is HOURS, not days)
        if 'Absence Type' not in df.columns:
            return df
        
        def calculate_days(row):
            if pd.isna(row.get('Absence Type')):
                return 0
            
            abs_type = str(row['Absence Type']).strip()
            
            if abs_type == 'Full Day':
                return 1.0
            elif abs_type in ['AM Half Day', 'PM Half Day']:
                return 0.5
            elif abs_type == 'Custom Duration':
                if 'Duration' in row:
                    hours = pd.to_numeric(row['Duration'], errors='coerce')
                    if pd.notna(hours):
                        return hours / 7.5
                return 0
            else:
                return 0
        
        df['Absence_Days'] = df.apply(calculate_days, axis=1)
        return df
    
    def process(self, df: pd.DataFrame, school_name: Optional[str] = None, blackboard_context: Optional[Dict] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Complete cleaning process with LLM reasoning.
        
        Args:
            df: DataFrame to clean
            school_name: Optional school name for context
            
        Returns:
            Tuple of (cleaned DataFrame, cleaning_stats with reasoning)
        """
        original_rows = len(df)
        stats = {
            'original_rows': original_rows,
            'after_validation': 0,
            'after_rule1': 0,
            'after_rule2': 0,
            'after_rule3': 0,
            'final_rows': 0,
            'rows_removed': 0,
            'llm_reasoning': None,
            'suggested_rules': None,
            'validation_report': None
        }
        
        # Step 0: Validate data format FIRST (before business rules)
        df, validation_report = self.validate_data_format(df)
        stats['after_validation'] = len(df)
        stats['validation_report'] = validation_report
        stats['rows_removed'] += validation_report.get('rows_removed', 0)
        
        # Step 1: LLM reasons about cleaning rules (with blackboard context)
        reasoning = self.reason_about_cleaning_rules(df, school_name, blackboard_context)
        stats['llm_reasoning'] = reasoning.get('reasoning', '')
        stats['suggested_rules'] = reasoning.get('suggested_rules', {})
        stats['data_quality_issues'] = reasoning.get('data_quality_issues', [])
        
        # Step 2: Apply Rule 1 (based on LLM suggestion)
        should_remove_unfilled = stats['suggested_rules'].get('remove_unfilled_no_substitute', True)
        df = self.apply_rule1(df, should_remove_unfilled)
        stats['after_rule1'] = len(df)
        
        # Step 3: Apply Rule 2 (Employee Type Filter)
        # IMPORTANT: If user already filtered Employee Types, respect their selection
        user_already_filtered = blackboard_context and blackboard_context.get('user_already_filtered_employee_types', False)
        user_selected_types = blackboard_context.get('user_selected_employee_types', None) if blackboard_context else None
        
        if user_already_filtered and user_selected_types:
            # User already filtered - don't filter again, just validate
            stats['after_rule2'] = len(df)  # No change, user already filtered
            stats['user_filtered_employee_types'] = user_selected_types
            stats['rule2_applied'] = False  # We didn't apply it, user did
        else:
            # User didn't filter - apply LLM reasoning
            employee_types = stats['suggested_rules'].get('employee_types_to_keep', 
                                                          ['Teacher', 'Teacher Music', 'Teacher SpecEd'])
            df = self.apply_rule2(df, employee_types)
            stats['after_rule2'] = len(df)
            stats['rule2_applied'] = True  # We applied it
            stats['llm_selected_employee_types'] = employee_types
        
        # Step 4: Apply Rule 3 (School Year Date Validation) - always apply when we have School Year + Date (matches test script)
        should_validate_dates = stats['suggested_rules'].get('validate_school_year_dates', True)
        if 'School Year' in df.columns and 'Date' in df.columns:
            should_validate_dates = True  # Force Rule 3 to match test_toms_river logic
        df = self.apply_rule3(df, should_validate_dates)
        stats['after_rule3'] = len(df)
        
        # Step 5: Calculate absence days (deterministic - it's math)
        df = self.calculate_absence_days(df)
        
        stats['final_rows'] = len(df)
        stats['rows_removed'] = original_rows - len(df)
        
        return df, stats
