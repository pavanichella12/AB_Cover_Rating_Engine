"""
FileUploadAgent - Handles CSV/Excel file uploads
Responsibility: Read and validate uploaded files
"""

import pandas as pd
from typing import Optional, Tuple


class FileUploadAgent:
    """
    Agent responsible for handling file uploads.
    
    Tasks:
    - Accept uploaded CSV/Excel files
    - Read file into pandas DataFrame
    - Validate file format
    - Return DataFrame or error message
    """
    
    def __init__(self):
        self.name = "FileUploadAgent"
        self.supported_formats = ['.csv', '.xlsx', '.xls']
    
    def process(self, uploaded_file) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Process uploaded file and return DataFrame.
        
        Args:
            uploaded_file: Streamlit UploadedFile object or file path
            
        Returns:
            Tuple of (DataFrame, error_message)
            - If successful: (DataFrame, None)
            - If error: (None, error_message)
        """
        try:
            # Get file extension
            file_name = uploaded_file.name if hasattr(uploaded_file, 'name') else str(uploaded_file)
            file_ext = file_name.lower().split('.')[-1]
            
            # Validate file format
            if file_ext not in ['csv', 'xlsx', 'xls']:
                return None, f"Unsupported file format: .{file_ext}. Supported: .csv, .xlsx, .xls"
            
            # Read file based on extension
            if file_ext == 'csv':
                df = pd.read_csv(uploaded_file)
            else:  # xlsx or xls
                df = pd.read_excel(uploaded_file)
            
            # Basic validation
            if df.empty:
                return None, "Uploaded file is empty"

            # Deduplicate columns (Excel/CSV can have duplicate headers) to avoid
            # "cannot assemble with duplicate keys" in downstream filter/date ops
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]

            return df, None
            
        except Exception as e:
            return None, f"Error reading file: {str(e)}"
    
    def get_file_info(self, df: pd.DataFrame) -> dict:
        """
        Get basic information about the uploaded file.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            Dictionary with file information
        """
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': df.columns.tolist(),
            'data_types': df.dtypes.to_dict(),
            'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        }
