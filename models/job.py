"""
Job Model - Represents a production job to be scheduled

This module defines the Job class which encapsulates all information about
a production job including its requirements, constraints, and priority.

Key Attributes:
    - job_id: Unique identifier
    - product_type: Type of product being manufactured (e.g., P_A, P_B)
    - processing_time: How long the job takes to complete (minutes)
    - due_time: Deadline for completion
    - priority: "rush" or "normal"
    - machine_options: List of compatible machines
"""

from datetime import datetime, time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import json


@dataclass
class Job:
    """
    Represents a single production job in the manufacturing system.
    
    Example:
        >>> job = Job(
        ...     job_id="J001",
        ...     product_type="P_A",
        ...     processing_time=45,
        ...     due_time=time(12, 0),
        ...     priority="rush",
        ...     machine_options=["M1", "M3"]
        ... )
    """
    
    job_id: str                          # Unique job identifier (e.g., "J001")
    product_type: str                    # Product family (e.g., "P_A", "P_B")
    processing_time: int                 # Processing duration in minutes
    due_time: time                       # Deadline time (e.g., 12:00 for noon)
    priority: str = "normal"             # "rush" or "normal"
    machine_options: List[str] = field(default_factory=list)  # Compatible machines
    
    # Optional fields for advanced features
    setup_requirements: Optional[str] = None    # Special setup needs
    operator_skill_required: Optional[str] = None  # Required operator skill level
    batch_size: int = 1                  # Number of units in this job
    
    def __post_init__(self):
        """Validate job data after initialization."""
        # Validate priority
        if self.priority not in ["rush", "normal"]:
            raise ValueError(f"Priority must be 'rush' or 'normal', got: {self.priority}")
        
        # Validate processing time
        if self.processing_time <= 0:
            raise ValueError(f"Processing time must be positive, got: {self.processing_time}")
        
        # Validate machine options
        if not self.machine_options:
            raise ValueError(f"Job {self.job_id} must have at least one machine option")
    
    @property
    def is_rush(self) -> bool:
        """Check if this is a rush order."""
        return self.priority == "rush"
    
    def can_run_on(self, machine_id: str) -> bool:
        """
        Check if this job can run on the specified machine.
        
        Args:
            machine_id: Machine identifier (e.g., "M1")
            
        Returns:
            True if compatible, False otherwise
        """
        return machine_id in self.machine_options
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert job to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the job
        """
        return {
            "job_id": self.job_id,
            "product_type": self.product_type,
            "processing_time": self.processing_time,
            "due_time": self.due_time.strftime("%H:%M") if isinstance(self.due_time, time) else str(self.due_time),
            "priority": self.priority,
            "machine_options": self.machine_options,
            "setup_requirements": self.setup_requirements,
            "operator_skill_required": self.operator_skill_required,
            "batch_size": self.batch_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """
        Create a Job instance from a dictionary.
        
        Args:
            data: Dictionary containing job data
            
        Returns:
            Job instance
        """
        # Parse due_time string to time object
        if isinstance(data.get('due_time'), str):
            hour, minute = map(int, data['due_time'].split(':'))
            data['due_time'] = time(hour, minute)
        
        return cls(**data)
    
    def __str__(self) -> str:
        """String representation for logging and debugging."""
        rush_flag = " [RUSH]" if self.is_rush else ""
        return (f"Job({self.job_id}: {self.product_type}, "
                f"{self.processing_time}min, due {self.due_time}{rush_flag})")
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (f"Job(job_id='{self.job_id}', product_type='{self.product_type}', "
                f"processing_time={self.processing_time}, due_time={self.due_time}, "
                f"priority='{self.priority}', machine_options={self.machine_options})")


# Example usage and testing
if __name__ == "__main__":
    # Create a rush order
    rush_job = Job(
        job_id="J001",
        product_type="P_A",
        processing_time=45,
        due_time=time(12, 0),
        priority="rush",
        machine_options=["M1", "M3"]
    )
    
    print(rush_job)
    print(f"Is rush? {rush_job.is_rush}")
    print(f"Can run on M1? {rush_job.can_run_on('M1')}")
    print(f"Can run on M2? {rush_job.can_run_on('M2')}")
    
    # Convert to dict and back
    job_dict = rush_job.to_dict()
    print(f"\nAs dict: {json.dumps(job_dict, indent=2)}")
    
    reconstructed = Job.from_dict(job_dict)
    print(f"\nReconstructed: {reconstructed}")
