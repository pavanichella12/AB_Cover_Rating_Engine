"""
RatingEngineAgent - Calculates Rating Engine metrics
Responsibility: Calculate premium and coverage metrics based on user inputs
"""

import pandas as pd
from typing import Dict, Optional, Tuple


class RatingEngineAgent:
    """
    Agent responsible for Rating Engine calculations.
    
    Tasks:
    - Accept user input variables (Deductible, CC Days, Replacement Cost, etc.)
    - Calculate staff counts in coverage ranges
    - Calculate total absence days
    - Calculate costs and premiums
    - Return results dictionary
    """
    
    def __init__(self):
        self.name = "RatingEngineAgent"
    
    def calculate_teacher_absence_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate total absence days per teacher per school year.
        
        Args:
            df: Cleaned DataFrame with Absence_Days column
            
        Returns:
            DataFrame with columns: School Year, Employee Identifier, Total_Days
        """
        if 'Absence_Days' not in df.columns:
            raise ValueError("DataFrame must have 'Absence_Days' column")
        
        # Group by School Year and Employee Identifier
        teacher_days = df.groupby(['School Year', 'Employee Identifier'])['Absence_Days'].sum().reset_index()
        teacher_days.columns = ['School Year', 'Employee Identifier', 'Total_Days']
        
        return teacher_days
    
    def calculate_coverage_metrics(
        self, 
        teacher_days: pd.DataFrame,
        deductible: int,
        cc_days: int,
        replacement_cost: float
    ) -> Dict:
        """
        Calculate Rating Engine metrics.
        
        Args:
            teacher_days: DataFrame with teacher absence days
            deductible: Waiting period (deductible) in days
            cc_days: Critical Coverage maximum days per teacher
            replacement_cost: Replacement cost per day
            
        Returns:
            Dictionary with calculated metrics
        """
        # Calculate total days per teacher (across all years or per year)
        total_days_per_teacher = teacher_days.groupby('Employee Identifier')['Total_Days'].sum()
        
        # CC Maximum = Deductible + CC Days
        cc_maximum = deductible + cc_days
        
        # 1. Staff in CC Range: > Deductible AND <= CC Maximum
        staff_in_cc_range = total_days_per_teacher[
            (total_days_per_teacher > deductible) & 
            (total_days_per_teacher <= cc_maximum)
        ]
        num_staff_cc_range = len(staff_in_cc_range)
        
        # 2. Total CC Days: Sum of days for staff in CC range
        # For each teacher in CC range, count all their days
        total_cc_days = staff_in_cc_range.sum()
        
        # 3. Replacement Cost × Total CC Days
        replacement_cost_cc = replacement_cost * total_cc_days
        
        # 4. High Claimant Staff: > CC Maximum
        high_claimant_staff = total_days_per_teacher[total_days_per_teacher > cc_maximum]
        num_high_claimant = len(high_claimant_staff)
        
        # 5. Total Excess Days: Days beyond CC Maximum for high claimants
        # For each high claimant, count only excess days (Total_Days - CC_Maximum)
        excess_days = (high_claimant_staff - cc_maximum).sum()
        
        # 6. Cost of High Claimant Staff
        high_claimant_cost = replacement_cost * excess_days
        
        return {
            'num_staff_cc_range': num_staff_cc_range,
            'total_cc_days': total_cc_days,
            'replacement_cost_cc': replacement_cost_cc,
            'num_high_claimant': num_high_claimant,
            'excess_days': excess_days,
            'high_claimant_cost': high_claimant_cost,
            'deductible': deductible,
            'cc_days': cc_days,
            'cc_maximum': cc_maximum,
            'replacement_cost': replacement_cost
        }
    
    def calculate_premium(
        self,
        replacement_cost_cc: float,
        ark_commission_rate: float,
        abcover_commission_rate: float
    ) -> Dict:
        """
        Calculate premium components.
        
        Args:
            replacement_cost_cc: Replacement cost × total CC days
            ark_commission_rate: ARK commission rate (e.g., 0.15 for 15%)
            abcover_commission_rate: ABCover commission rate (e.g., 0.15 for 15%)
            
        Returns:
            Dictionary with premium calculations
        """
        ark_commission = replacement_cost_cc * ark_commission_rate
        abcover_commission = replacement_cost_cc * abcover_commission_rate
        total_premium = replacement_cost_cc + ark_commission + abcover_commission
        
        return {
            'replacement_cost_cc': replacement_cost_cc,
            'ark_commission': ark_commission,
            'abcover_commission': abcover_commission,
            'total_premium': total_premium
        }
    
    def process(
        self,
        df: pd.DataFrame,
        deductible: int,
        cc_days: int,
        replacement_cost: float,
        ark_commission_rate: float,
        abcover_commission_rate: float,
        school_year_days: Optional[int] = None
    ) -> Tuple[Dict, Optional[str]]:
        """
        Complete Rating Engine calculation process.
        
        Args:
            df: Cleaned DataFrame
            deductible: Deductible (waiting period) in days
            cc_days: Critical Coverage days per teacher
            replacement_cost: Replacement cost per day
            ark_commission_rate: ARK commission rate (0.15 = 15%)
            abcover_commission_rate: ABCover commission rate (0.15 = 15%)
            school_year_days: Optional school year days (for reference)
            
        Returns:
            Tuple of (results_dict, error_message)
        """
        try:
            # Calculate teacher absence days
            teacher_days = self.calculate_teacher_absence_days(df)
            
            # Calculate coverage metrics
            coverage_metrics = self.calculate_coverage_metrics(
                teacher_days,
                deductible,
                cc_days,
                replacement_cost
            )
            
            # Calculate premium
            premium_metrics = self.calculate_premium(
                coverage_metrics['replacement_cost_cc'],
                ark_commission_rate,
                abcover_commission_rate
            )
            
            # Combine all results
            results = {
                **coverage_metrics,
                **premium_metrics,
                'school_year_days': school_year_days
            }
            
            return results, None
            
        except Exception as e:
            return {}, f"Error calculating metrics: {str(e)}"
