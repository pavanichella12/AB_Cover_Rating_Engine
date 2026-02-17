"""
RatingEngineAgentLLM - LLM-powered agent for Rating Engine calculations
Responsibility: Reason about calculations, adapt to school-specific logic
"""

import pandas as pd
from typing import Dict, Any, Optional, Tuple
from .llm_agent_base import LLMAgentBase
import json


class RatingEngineAgentLLM(LLMAgentBase):
    """
    LLM-powered agent for Rating Engine calculations.
    
    Tasks:
    - Understand Rating Engine logic from Excel template
    - Reason about school-specific calculation differences
    - Calculate metrics with adaptive logic
    - Explain calculation decisions
    """
    
    def __init__(self, model_provider: str = "google", model_name: Optional[str] = None):
        super().__init__("RatingEngineAgentLLM", model_provider, model_name)
        # Load Rating Engine template context
        self.rating_engine_context = self._load_rating_engine_context()
    
    def _get_system_prompt(self) -> str:
        return """You are a Rating Engine calculation expert for ABCover's school absence insurance system.

YOUR EXPERTISE (Based on Rating Engine Excel template and EDA analysis):
You understand the Rating Engine calculation logic from the Excel template and have analyzed multiple schools' data patterns.

RATING ENGINE CALCULATION LOGIC (From Excel Template):

1. TEACHER ABSENCE DAYS CALCULATION:
   - Group by: School Year + Employee Identifier
   - Sum: Total Absence_Days per teacher per school year
   - Then aggregate: Total days per teacher across all years (or per year)
   - Standard calculation: Full Day=1.0, Half Day=0.5, Custom Duration=hours/7.5

2. STAFF IN CC RANGE:
   - Count teachers where: Total Absence Days > Deductible AND ≤ (Deductible + CC Days)
   - Example: If Deductible=20, CC Days=60, then CC Maximum=80
   - Count teachers with absences between 21-80 days
   - This represents staff who need Critical Coverage

3. TOTAL CC DAYS:
   - IMPORTANT: Count ONLY days in CC range (Greater than Deductible BUT Less than or = to CC Maximum)
   - Formula: For each teacher in CC range, count (Total_Days - Deductible) up to CC Maximum
   - Example: Teacher has 50 days, Deductible=20, CC Max=80 → Count only 30 days (50-20)
   - Example: Teacher has 100 days, Deductible=20, CC Max=80 → Count only 60 days (80-20, capped at CC Max)
   - This represents the days that fall within the Critical Coverage window

4. REPLACEMENT COST × CC DAYS:
   - Base calculation: Replacement Cost per Day × Total CC Days
   - This is the cost to cover CC range staff

5. HIGH CLAIMANT STAFF:
   - Count teachers where: Total Absence Days > (Deductible + CC Days)
   - Example: Teachers with > 80 days (if Deductible=20, CC=60)

6. EXCESS DAYS:
   - For high claimant staff, count days beyond CC Maximum
   - CRITICAL DECISION POINT: Count only excess or all days?
   - Standard approach: Count only excess days (Total_Days - CC_Maximum)
   - Example: If teacher has 100 days and CC Max=80, count 20 excess days
   - Alternative: Count all days for high claimants

7. HIGH CLAIMANT COST:
   - Replacement Cost × Excess Days
   - Cost for days beyond CC coverage

8. PREMIUM CALCULATION:
   - Base: Replacement Cost × Total CC Days
   - ARK Commission: Base × ARK Commission Rate (typically 15%)
   - ABCover Commission: Base × ABCover Commission Rate (typically 15%)
   - Total Premium: Base + ARK Commission + ABCover Commission

CALCULATION APPROACH (Fixed - based on Excel template):

For "Total CC Days":
- ALWAYS use: Count only days in CC range (Greater than Deductible BUT Less than or = to CC Maximum)
  - This is the standard approach from the Excel template
  - Formula: For each teacher, count (Total_Days - Deductible) but cap at (CC Maximum - Deductible)
  - Example: Teacher with 50 days, Deductible=20, CC Max=80 → Count 30 days (50-20)
  - Example: Teacher with 100 days, Deductible=20, CC Max=80 → Count 60 days (80-20, not 100-20)

For "Excess Days":
- Option A (Standard): Count only excess beyond CC Maximum
  - REASON: School already covered up to CC Maximum, only excess needs coverage
  - Example: Teacher with 100 days, CC Max=80 → count 20 excess days
  
- Option B (Alternative): Count all days for high claimants
  - REASON: High claimants need full coverage
  - Example: Teacher with 100 days → count all 100 days

YOUR TASK:
1. Analyze the school's data patterns
2. Look at distribution of teacher absence days
3. Reason about which calculation approach makes sense
4. Consider: What would be fair? What matches the Rating Engine Excel logic?
5. Explain your reasoning clearly

TYPICAL PATTERNS YOU'VE SEEN:
- Most teachers have 0-20 days (below deductible)
- Some teachers have 21-80 days (CC range)
- Few teachers have >80 days (high claimants)
- Distribution varies by school

Always reason about which approach aligns with the Rating Engine Excel template logic and makes business sense.
Respond with clear calculations, reasoning, and explanations."""
    
    def _load_rating_engine_context(self) -> str:
        """Load context about Rating Engine from Excel template."""
        return """
Rating Engine Calculation Logic (from Excel Template):

1. Staff in CC Range:
   - Count teachers where: Total Absence Days > Deductible AND ≤ (Deductible + CC Days)
   - Example: If Deductible=20, CC Days=60, then count teachers with 21-80 days

2. Total CC Days:
   - Sum of absence days for staff in CC range
   - Question: Count all days or only days in CC range? (This may vary by school)

3. Replacement Cost × CC Days:
   - Replacement Cost per Day × Total CC Days

4. High Claimant Staff:
   - Count teachers where: Total Absence Days > (Deductible + CC Days)
   - Example: Teachers with > 80 days

5. Excess Days:
   - For high claimant staff, count days beyond CC Maximum
   - Example: If teacher has 100 days and CC Max=80, count 20 excess days

6. High Claimant Cost:
   - Replacement Cost × Excess Days

7. Premium Calculation:
   - Base: Replacement Cost × Total CC Days
   - ARK Commission: Base × ARK Commission Rate
   - ABCover Commission: Base × ABCover Commission Rate
   - Total Premium: Base + ARK Commission + ABCover Commission
"""
    
    def reason_about_calculations(
        self,
        teacher_days: pd.DataFrame,
        deductible: int,
        cc_days: int,
        replacement_cost: float,
        school_name: Optional[str] = None,
        blackboard_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to reason about the appropriate calculation approach.
        
        Args:
            teacher_days: DataFrame with teacher absence days
            deductible: Deductible in days
            cc_days: CC Days per teacher
            replacement_cost: Replacement cost per day
            school_name: Optional school name
            
        Returns:
            Dictionary with reasoning and recommended approach
        """
        # Prepare data summary
        total_teachers = len(teacher_days)
        total_days = teacher_days['Total_Days'].sum()
        avg_days = teacher_days['Total_Days'].mean()
        max_days = teacher_days['Total_Days'].max()
        cc_maximum = deductible + cc_days
        
        # Teachers in different ranges
        below_deductible = len(teacher_days[teacher_days['Total_Days'] <= deductible])
        in_cc_range = len(teacher_days[
            (teacher_days['Total_Days'] > deductible) & 
            (teacher_days['Total_Days'] <= cc_maximum)
        ])
        high_claimant = len(teacher_days[teacher_days['Total_Days'] > cc_maximum])
        
        # Add blackboard context if available
        context_info = ""
        if blackboard_context:
            context_info = f"""
BLACKBOARD CONTEXT (Full workflow history - you can see everything):
- Raw Data: {blackboard_context.get('raw_data_rows', 0):,} rows
- Selected Data: {blackboard_context.get('selected_data_rows', 0):,} rows  
- Cleaned Data: {blackboard_context.get('cleaned_data_rows', 0):,} rows
- Cleaning Reasoning: {blackboard_context.get('cleaning_reasoning', 'N/A')[:100]}...
- You have access to the complete data pipeline and can see what cleaning rules were applied and why.
"""
        
        prompt = f"""Analyze this school's absence data and reason about the appropriate Rating Engine calculation approach:

School: {school_name or 'Unknown'}
{context_info}
Total Teachers: {total_teachers}
Total Absence Days: {total_days:.2f}
Average Days per Teacher: {avg_days:.2f}
Max Days (single teacher): {max_days:.2f}

Deductible: {deductible} days
CC Days: {cc_days} days
CC Maximum: {cc_maximum} days
Replacement Cost: ${replacement_cost:.2f} per day

Teacher Distribution:
- Below Deductible (≤{deductible} days): {below_deductible} teachers
- In CC Range ({deductible+1}-{cc_maximum} days): {in_cc_range} teachers
- High Claimant (>{cc_maximum} days): {high_claimant} teachers

{self.rating_engine_context}

IMPORTANT CALCULATION RULES (Fixed - based on Excel template):
1. Total CC Days: ALWAYS count only days in CC range (Greater than Deductible BUT ≤ CC Maximum)
   - Formula: For each teacher, count (Total_Days - Deductible) but cap at (CC Maximum - Deductible)
   - Example: Teacher with 50 days, Deductible=20, CC Max=80 → Count 30 days (50-20)
   
2. Excess Days: Count only excess beyond CC Maximum for high claimants
   - Formula: For each high claimant, count (Total_Days - CC Maximum)
   - Example: Teacher with 100 days, CC Max=80 → Count 20 excess days

Questions to reason about:
1. Are there any school-specific considerations or data patterns that should be noted?
2. Does the data distribution look reasonable for this school?
3. Any anomalies or outliers that need attention?

Provide your reasoning and analysis in JSON format:
{{
    "reasoning": "Your analysis of the school's data patterns and distribution",
    "data_quality_assessment": "Any issues or anomalies found",
    "calculation_validation": "Confirmation that calculations follow Excel template logic",
    "school_specific_notes": "Any school-specific considerations or patterns observed"
}}

Note: Calculation approach is FIXED based on Excel template:
- Total CC Days: Always count only days in CC range (range_only)
- Excess Days: Always count only excess beyond CC Maximum (excess_only)
"""
        
        llm_response = self._call_llm(prompt)
        
        try:
            reasoning = json.loads(llm_response)
            # Ensure calculation approach is set correctly (fixed based on Excel template)
            if "recommended_approach" not in reasoning:
                reasoning["recommended_approach"] = {
                    "cc_days_calculation": "range_only",  # Fixed: always count only days in CC range
                    "excess_days_calculation": "excess_only",  # Fixed: always count only excess
                    "explanation": "Fixed approach based on Excel template"
                }
        except json.JSONDecodeError:
            reasoning = {
                "reasoning": llm_response,
                "recommended_approach": {
                    "cc_days_calculation": "range_only",  # Fixed: always count only days in CC range
                    "excess_days_calculation": "excess_only",  # Fixed: always count only excess
                    "explanation": "Fixed approach based on Excel template"
                },
                "school_specific_notes": ""
            }
        
        return reasoning
    
    def calculate_with_reasoning(
        self,
        teacher_days: pd.DataFrame,
        cleaned_data: pd.DataFrame,
        deductible: int,
        cc_days: int,
        replacement_cost: float,
        ark_commission_rate: float,
        abcover_commission_rate: float,
        school_name: Optional[str] = None,
        calculation_approach: Optional[Dict] = None,
        blackboard_context: Optional[Dict] = None,
        school_year_days: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Calculate Rating Engine metrics with LLM reasoning.
        
        Args:
            teacher_days: DataFrame with teacher absence days (aggregated)
            cleaned_data: Full cleaned DataFrame (to count staff and absences per school year)
            deductible: Deductible in days
            cc_days: CC Days per teacher
            replacement_cost: Replacement cost per day
            ark_commission_rate: ARK commission rate
            abcover_commission_rate: ABCover commission rate
            school_name: Optional school name
            calculation_approach: Optional pre-determined approach
            blackboard_context: Full workflow context
            school_year_days: School year days (for reference)
            
        Returns:
            Tuple of (results_dict, reasoning_dict)
        """
        # Get reasoning if not provided
        if calculation_approach is None:
            reasoning = self.reason_about_calculations(
                teacher_days, deductible, cc_days, replacement_cost, school_name, blackboard_context
            )
            calculation_approach = reasoning.get("recommended_approach", {})
        else:
            reasoning = {"recommended_approach": calculation_approach}
        
        # Ensure calculation approach is correct (fixed based on Excel template)
        calculation_approach["cc_days_calculation"] = "range_only"  # Always count only days in CC range
        calculation_approach["excess_days_calculation"] = "excess_only"  # Always count only excess
        
        # ============================================================================
        # CALCULATE PER-SCHOOL-YEAR METRICS (from cleaned data)
        # ============================================================================
        # These metrics are calculated from cleaned_data (after user selection and cleaning)
        per_school_year_metrics = {}
        
        if 'School Year' in cleaned_data.columns:
            # Group by School Year
            for school_year in cleaned_data['School Year'].unique():
                if pd.isna(school_year):
                    continue
                    
                sy_data = cleaned_data[cleaned_data['School Year'] == school_year]
                
                # Total # Of Staff (unique Employee Identifiers per school year)
                total_staff = sy_data['Employee Identifier'].nunique() if 'Employee Identifier' in sy_data.columns else 0
                
                # Total # of Absences = sum of actual days (Absence_Days), not row count
                total_absences = float(sy_data['Absence_Days'].sum()) if 'Absence_Days' in sy_data.columns else len(sy_data)
                
                # Total Replacement Cost to District (Total Absence Days × Replacement Cost Per Day)
                total_replacement_cost = total_absences * replacement_cost
                
                per_school_year_metrics[str(school_year)] = {
                    'total_staff': int(total_staff),
                    'total_absences': float(total_absences),
                    'total_replacement_cost': float(total_replacement_cost)
                }
        
        # Calculate overall totals (across all school years) - use actual days, not row count
        overall_total_staff = cleaned_data['Employee Identifier'].nunique() if 'Employee Identifier' in cleaned_data.columns else 0
        overall_total_absences = float(cleaned_data['Absence_Days'].sum()) if 'Absence_Days' in cleaned_data.columns else len(cleaned_data)
        overall_total_replacement_cost = overall_total_absences * replacement_cost
        
        # Perform calculations based on recommended approach
        cc_maximum = deductible + cc_days
        total_days_per_teacher = teacher_days.groupby('Employee Identifier')['Total_Days'].sum()
        
        # Staff in CC Range
        staff_in_cc_range = total_days_per_teacher[
            (total_days_per_teacher > deductible) & 
            (total_days_per_teacher <= cc_maximum)
        ]
        num_staff_cc_range = len(staff_in_cc_range)
        
        # Total CC Days: Count ONLY days in CC range (Greater than Deductible BUT ≤ CC Maximum)
        # Formula: For each teacher, count (Total_Days - Deductible) but cap at (CC Maximum - Deductible)
        total_cc_days = 0
        cc_range_details = []  # For debugging/validation
        for emp_id, days in staff_in_cc_range.items():
            if days > deductible:
                # Count days in CC range: (days - deductible), but max is (cc_maximum - deductible)
                days_in_range = min(days - deductible, cc_maximum - deductible)
                total_cc_days += days_in_range
                cc_range_details.append({
                    'employee_id': emp_id,
                    'total_days': days,
                    'days_in_cc_range': days_in_range,
                    'calculation': f"min({days} - {deductible}, {cc_maximum} - {deductible}) = {days_in_range}"
                })
        
        # Replacement Cost × CC Days
        replacement_cost_cc = replacement_cost * total_cc_days
        
        # High Claimant Staff
        high_claimant_staff = total_days_per_teacher[total_days_per_teacher > cc_maximum]
        num_high_claimant = len(high_claimant_staff)
        
        # Excess Days (based on approach)
        high_claimant_details = []  # For debugging/validation
        if calculation_approach.get("excess_days_calculation") == "all_days":
            # Count all days for high claimants
            excess_days = high_claimant_staff.sum()
            for emp_id, days in high_claimant_staff.items():
                high_claimant_details.append({
                    'employee_id': emp_id,
                    'total_days': days,
                    'excess_days': days,
                    'calculation': f"All days counted: {days}"
                })
        else:  # excess_only (default)
            # Count only excess beyond CC Maximum
            excess_days = (high_claimant_staff - cc_maximum).sum()
            for emp_id, days in high_claimant_staff.items():
                excess = days - cc_maximum
                high_claimant_details.append({
                    'employee_id': emp_id,
                    'total_days': days,
                    'excess_days': excess,
                    'calculation': f"{days} - {cc_maximum} = {excess}"
                })
        
        # High Claimant Cost
        high_claimant_cost = replacement_cost * excess_days
        
        # Premium Calculation
        ark_commission = replacement_cost_cc * ark_commission_rate
        abcover_commission = replacement_cost_cc * abcover_commission_rate
        total_premium = replacement_cost_cc + ark_commission + abcover_commission
        
        results = {
            # Per-School-Year Metrics (from cleaned data)
            'per_school_year_metrics': per_school_year_metrics,
            'overall_total_staff': int(overall_total_staff),
            'overall_total_absences': int(overall_total_absences),
            'overall_total_replacement_cost': float(overall_total_replacement_cost),
            
            # CC Range Metrics
            'num_staff_cc_range': num_staff_cc_range,
            'total_cc_days': total_cc_days,
            'replacement_cost_cc': replacement_cost_cc,
            'cc_range_details': cc_range_details,  # For validation/debugging
            
            # High Claimant Metrics
            'num_high_claimant': num_high_claimant,
            'excess_days': excess_days,
            'high_claimant_cost': high_claimant_cost,
            'high_claimant_details': high_claimant_details,  # For validation/debugging
            
            # Premium Calculation
            'ark_commission': ark_commission,
            'abcover_commission': abcover_commission,
            'total_premium': total_premium,
            
            # Input Parameters (for reference)
            'deductible': deductible,
            'cc_days': cc_days,
            'cc_maximum': cc_maximum,
            'replacement_cost': replacement_cost,
            'school_year_days': school_year_days,
            'calculation_approach': calculation_approach,
            
            # Debug info
            'total_teachers': len(total_days_per_teacher),
            'below_deductible_count': len(total_days_per_teacher[total_days_per_teacher <= deductible])
        }
        
        return results, reasoning
    
    def process(
        self,
        teacher_days: pd.DataFrame,
        cleaned_data: pd.DataFrame,
        deductible: int,
        cc_days: int,
        replacement_cost: float,
        ark_commission_rate: float,
        abcover_commission_rate: float,
        school_name: Optional[str] = None,
        blackboard_context: Optional[Dict] = None,
        school_year_days: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Complete Rating Engine calculation process with LLM reasoning.
        
        Args:
            teacher_days: DataFrame with teacher absence days (aggregated from cleaned data)
            cleaned_data: Full cleaned DataFrame (to count staff and absences per school year)
            deductible: Deductible in days (waiting period)
            cc_days: CC Days per teacher (maximum coverage)
            replacement_cost: Replacement cost per day
            ark_commission_rate: ARK commission rate
            abcover_commission_rate: ABCover commission rate
            school_name: Optional school name
            blackboard_context: Full workflow context (can see cleaning steps)
            school_year_days: School year days (for reference/validation)
            
        Returns:
            Tuple of (results_dict, reasoning_dict)
        """
        return self.calculate_with_reasoning(
            teacher_days, cleaned_data, deductible, cc_days, replacement_cost,
            ark_commission_rate, abcover_commission_rate, school_name, None, blackboard_context, school_year_days
        )
