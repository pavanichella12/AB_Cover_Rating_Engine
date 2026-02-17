"""
DataSelectionAgent - Handles column and row selection
Responsibility: Let user select which columns/rows to keep
"""

import pandas as pd
from typing import List, Optional, Dict, Tuple


class DataSelectionAgent:
    """
    Agent responsible for data selection (columns and rows).
    
    Tasks:
    - Show available columns
    - Let user select columns to keep
    - Let user filter rows (by date, employee type, etc.)
    - Return filtered DataFrame
    """
    
    def __init__(self):
        self.name = "DataSelectionAgent"
    
    def get_available_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of available columns in the DataFrame."""
        return df.columns.tolist()
    
    def select_columns(self, df: pd.DataFrame, selected_columns: List[str]) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Select specific columns from DataFrame.
        
        Args:
            df: Original DataFrame
            selected_columns: List of column names to keep
            
        Returns:
            Tuple of (filtered DataFrame, error_message)
        """
        try:
            # Validate selected columns exist
            missing_cols = [col for col in selected_columns if col not in df.columns]
            if missing_cols:
                return df, f"Warning: Columns not found: {missing_cols}"
            
            # Deduplicate selected_columns to avoid duplicate column names in result
            seen = set()
            unique_cols = [c for c in selected_columns if c not in seen and not seen.add(c)]
            
            # Select columns
            filtered_df = df[unique_cols].copy()
            # Deduplicate in case df had duplicate column names (df[cols] can return dups)
            if filtered_df.columns.duplicated().any():
                filtered_df = filtered_df.loc[:, ~filtered_df.columns.duplicated()]

            if filtered_df.empty:
                return df, "Warning: No data after column selection"
            
            return filtered_df, None
            
        except Exception as e:
            return df, f"Error selecting columns: {str(e)}"
    
    def filter_rows(self, df: pd.DataFrame, filters: Dict) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Apply row filters to DataFrame.
        
        Args:
            df: DataFrame to filter
            filters: Dictionary with filter criteria
                Example: {
                    'date_range': (start_date, end_date),
                    'employee_type': ['Teacher', 'Teacher Music'],
                    'filled_status': ['Filled'],
                    'school_year': ['2020-2021', '2021-2022']
                }
        
        Returns:
            Tuple of (filtered DataFrame, error_message)
        """
        try:
            filtered_df = df.copy()
            
            # Deduplicate columns - pandas raises "cannot assemble with duplicate keys" when
            # to_datetime/isin get multiple columns with same name (e.g. after rename collisions)
            if filtered_df.columns.duplicated().any():
                filtered_df = filtered_df.loc[:, ~filtered_df.columns.duplicated()]
            
            # Filter by date range
            if 'date_range' in filters and filters['date_range']:
                start_date, end_date = filters['date_range']
                if 'Date' in filtered_df.columns:
                    # Convert date_range to datetime if needed
                    if not pd.api.types.is_datetime64_any_dtype(filtered_df['Date']):
                        filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
                    
                    # Convert start_date and end_date to Timestamp for comparison
                    start_date = pd.Timestamp(start_date) if start_date else None
                    end_date = pd.Timestamp(end_date) if end_date else None
                    
                    if start_date and end_date:
                        filtered_df = filtered_df[
                            (filtered_df['Date'] >= start_date) & 
                            (filtered_df['Date'] <= end_date)
                        ]
            
            # Filter by employee type
            if 'employee_type' in filters and filters['employee_type']:
                if 'Employee Type' in filtered_df.columns:
                    filtered_df = filtered_df[
                        filtered_df['Employee Type'].isin(filters['employee_type'])
                    ]
            
            # Filter by filled status
            if 'filled_status' in filters and filters['filled_status']:
                if 'Filled' in filtered_df.columns:
                    filtered_df = filtered_df[
                        filtered_df['Filled'].isin(filters['filled_status'])
                    ]
            
            # Filter by school year
            if 'school_year' in filters and filters['school_year']:
                if 'School Year' in filtered_df.columns:
                    filtered_df = filtered_df[
                        filtered_df['School Year'].isin(filters['school_year'])
                    ]
            
            if filtered_df.empty:
                return df, "Warning: No data after applying filters"
            
            return filtered_df, None
            
        except Exception as e:
            return df, f"Error filtering rows: {str(e)}"
    
    def process(self, df: pd.DataFrame, selected_columns: List[str], filters: Optional[Dict] = None) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Complete selection process: columns + rows.
        
        Args:
            df: Original DataFrame
            selected_columns: Columns to keep
            filters: Optional row filters
            
        Returns:
            Tuple of (filtered DataFrame, error_message)
        """
        # First select columns
        df_filtered, error = self.select_columns(df, selected_columns)
        if error:
            return df_filtered, error
        
        # Then apply row filters if provided
        if filters:
            df_filtered, error = self.filter_rows(df_filtered, filters)
            if error:
                return df_filtered, error
        
        return df_filtered, None
