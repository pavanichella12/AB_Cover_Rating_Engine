"""
DataCleaningAgent - Applies data cleaning rules
Responsibility: Clean and filter data according to business rules
"""

import pandas as pd
from typing import Optional, Tuple


class DataCleaningAgent:
    """
    Agent responsible for data cleaning.
    
    Tasks:
    - Apply Rule 1: Remove records where Filled='Unfilled' AND Needs Substitute='NO'
    - Apply Rule 2: Keep only Teacher, Teacher Music, Teacher SpecEd
    - Calculate Absence Days
    - Return cleaned DataFrame
    """
    
    def __init__(self):
        self.name = "DataCleaningAgent"
        self.teacher_types = ['Teacher', 'Teacher Music', 'Teacher SpecEd']
    
    def apply_rule1(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rule 1: Remove records where Filled='Unfilled' AND Needs Substitute='NO'
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        if 'Filled' in df.columns and 'Needs Substitute' in df.columns:
            # Keep records that are NOT (Unfilled AND NO)
            mask = ~((df['Filled'] == 'Unfilled') & (df['Needs Substitute'] == 'NO'))
            return df[mask].copy()
        return df.copy()
    
    def apply_rule2(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rule 2: Keep only Teacher, Teacher Music, Teacher SpecEd
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Cleaned DataFrame
        """
        if 'Employee Type' in df.columns:
            return df[df['Employee Type'].isin(self.teacher_types)].copy()
        return df.copy()
    
    def calculate_absence_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate absence days based on Absence Type.
        
        Logic:
        - Full Day = 1.0 day
        - AM Half Day / PM Half Day = 0.5 day
        - Custom Duration = hours / 7.5
        
        Args:
            df: DataFrame with Absence Type column
            
        Returns:
            DataFrame with 'Absence_Days' column added
        """
        df = df.copy()
        
        if 'Absence_Days' in df.columns:
            return df  # Already calculated
        
        def calculate_days(row):
            if pd.isna(row.get('Absence Type')):
                return 0
            
            abs_type = str(row['Absence Type']).strip()
            
            if abs_type == 'Full Day':
                return 1.0
            elif abs_type in ['AM Half Day', 'PM Half Day']:
                return 0.5
            elif abs_type == 'Custom Duration':
                # Try to get duration in hours
                if 'Duration' in row:
                    hours = pd.to_numeric(row['Duration'], errors='coerce')
                    if pd.notna(hours):
                        return hours / 7.5
                return 0
            else:
                return 0
        
        df['Absence_Days'] = df.apply(calculate_days, axis=1)
        return df
    
    def process(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """
        Apply all cleaning rules.
        
        Args:
            df: DataFrame to clean
            
        Returns:
            Tuple of (cleaned DataFrame, cleaning_stats)
        """
        original_rows = len(df)
        stats = {
            'original_rows': original_rows,
            'after_rule1': 0,
            'after_rule2': 0,
            'final_rows': 0,
            'rows_removed': 0
        }
        
        # Apply Rule 1
        df = self.apply_rule1(df)
        stats['after_rule1'] = len(df)
        
        # Apply Rule 2
        df = self.apply_rule2(df)
        stats['after_rule2'] = len(df)
        
        # Calculate absence days
        df = self.calculate_absence_days(df)
        
        stats['final_rows'] = len(df)
        stats['rows_removed'] = original_rows - len(df)
        
        return df, stats
