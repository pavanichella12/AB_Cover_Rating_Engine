"""
Blackboard Pattern - Shared Memory for Multi-Agent System
All agents read/write to this shared workspace
"""

from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime


class Blackboard:
    """
    Shared memory workspace for agents.
    Agents can read/write data, reasoning, and results here.
    """
    
    def __init__(self):
        """Initialize empty blackboard."""
        self.data: Dict[str, Any] = {
            "raw_data": None,
            "selected_data": None,
            "cleaned_data": None,
            "analysis": None,
            "cleaning_reasoning": None,
            "cleaning_rules": None,
            "calculations": None,
            "results": None,
            "metadata": {
                "school_name": None,
                "upload_timestamp": None,
                "processing_history": []
            }
        }
    
    def write(self, key: str, value: Any, agent_name: Optional[str] = None) -> None:
        """
        Write data to blackboard.
        
        Args:
            key: Key to store data under
            value: Data to store
            agent_name: Optional agent name for logging
        """
        self.data[key] = value
        
        # Log the write operation
        if agent_name:
            self.data["metadata"]["processing_history"].append({
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "action": f"wrote {key}",
                "data_type": type(value).__name__
            })
    
    def read(self, key: str) -> Any:
        """
        Read data from blackboard.
        
        Args:
            key: Key to read
            
        Returns:
            Data stored under key, or None if not found
        """
        return self.data.get(key)
    
    def read_all(self) -> Dict[str, Any]:
        """Read all data from blackboard."""
        return self.data.copy()
    
    def has(self, key: str) -> bool:
        """Check if key exists in blackboard."""
        return key in self.data and self.data[key] is not None
    
    def get_context_summary(self) -> str:
        """
        Get a summary of all data in blackboard for LLM context.
        
        Returns:
            String summary of blackboard contents
        """
        summary = []
        summary.append("=== BLACKBOARD CONTEXT ===\n")
        
        if self.has("raw_data"):
            df = self.data["raw_data"]
            summary.append(f"Raw Data: {len(df):,} rows, {len(df.columns)} columns")
        
        if self.has("selected_data"):
            df = self.data["selected_data"]
            summary.append(f"Selected Data: {len(df):,} rows, {len(df.columns)} columns")
        
        if self.has("cleaned_data"):
            df = self.data["cleaned_data"]
            summary.append(f"Cleaned Data: {len(df):,} rows")
        
        if self.has("analysis"):
            summary.append(f"Analysis: Available")
        
        if self.has("cleaning_reasoning"):
            summary.append(f"Cleaning Reasoning: Available")
        
        if self.has("cleaning_rules"):
            summary.append(f"Cleaning Rules: Available")
        
        if self.has("calculations"):
            summary.append(f"Calculations: Available")
        
        if self.has("results"):
            summary.append(f"Results: Available")
        
        summary.append(f"\nSchool: {self.data['metadata']['school_name'] or 'Unknown'}")
        summary.append(f"Processing Steps: {len(self.data['metadata']['processing_history'])}")
        
        return "\n".join(summary)
    
    def clear(self) -> None:
        """Clear all data from blackboard."""
        self.__init__()
    
    def get_history(self) -> list:
        """Get processing history."""
        return self.data["metadata"]["processing_history"].copy()
