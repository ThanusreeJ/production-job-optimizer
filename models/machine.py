"""
Machine Model - Represents production machines and constraints

This module defines the Machine class and Constraint class for representing
manufacturing equipment and operational constraints.

Key Features:
    - Machine capacity and capabilities
    - Downtime window management
    - Setup time matrices between product types
    - Shift boundaries and overtime rules
"""

from datetime import time, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import json


@dataclass
class DowntimeWindow:
    """
    Represents a scheduled downtime period for a machine.
    
    Used for maintenance, breakdowns, or shift changes.
    """
    start_time: time      # When downtime starts
    end_time: time        # When downtime ends
    reason: str = "Maintenance"  # Why the machine is down
    
    def overlaps_with(self, start: time, end: time) -> bool:
        """
        Check if this downtime overlaps with a given time window.
        
        Args:
            start: Start time to check
            end: End time to check
            
        Returns:
            True if there's overlap, False otherwise
        """
        # Convert times to minutes since midnight for comparison
        dt_start = self.start_time.hour * 60 + self.start_time.minute
        dt_end = self.end_time.hour * 60 + self.end_time.minute
        check_start = start.hour * 60 + start.minute
        check_end = end.hour * 60 + end.minute
        
        # Check for overlap
        return not (check_end <= dt_start or check_start >= dt_end)
    
    def __str__(self) -> str:
        return f"Downtime({self.start_time}-{self.end_time}: {self.reason})"


@dataclass
class Machine:
    """
    Represents a production machine with its constraints and capabilities.
    
    Example:
        >>> machine = Machine(
        ...     machine_id="M1",
        ...     capabilities=["P_A", "P_B"],
        ...     capacity_per_hour=60,
        ...     downtime_windows=[
        ...         DowntimeWindow(time(10, 0), time(11, 30), "Scheduled Maintenance")
        ...     ]
        ... )
    """
    
    machine_id: str                      # Unique identifier (e.g., "M1")
    capabilities: List[str]              # Product types this machine can handle
    capacity_per_hour: int = 60          # Max minutes of work per hour
    downtime_windows: List[DowntimeWindow] = field(default_factory=list)
    
    # Optional advanced features
    max_continuous_runtime: Optional[int] = None  # Max minutes before rest needed
    operator_id: Optional[str] = None    # Assigned operator
    
    def can_produce(self, product_type: str) -> bool:
        """
        Check if this machine can produce the specified product type.
        
        Args:
            product_type: Product identifier (e.g., "P_A")
            
        Returns:
            True if capable, False otherwise
        """
        return product_type in self.capabilities
    
    def is_available_at(self, time_slot: time) -> bool:
        """
        Check if machine is available (not in downtime) at specific time.
        
        Args:
            time_slot: Time to check
            
        Returns:
            True if available, False if in downtime
        """
        # Check against all downtime windows
        slot_minutes = time_slot.hour * 60 + time_slot.minute
        
        for downtime in self.downtime_windows:
            dt_start = downtime.start_time.hour * 60 + downtime.start_time.minute
            dt_end = downtime.end_time.hour * 60 + downtime.end_time.minute
            
            if dt_start <= slot_minutes < dt_end:
                return False
        
        return True
    
    def add_downtime(self, start: time, end: time, reason: str = "Unplanned"):
        """
        Add a downtime window to this machine.
        
        Args:
            start: Downtime start time
            end: Downtime end time
            reason: Reason for downtime
        """
        self.downtime_windows.append(DowntimeWindow(start, end, reason))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert machine to dictionary."""
        return {
            "machine_id": self.machine_id,
            "capabilities": self.capabilities,
            "capacity_per_hour": self.capacity_per_hour,
            "downtime_windows": [
                {
                    "start_time": dt.start_time.strftime("%H:%M"),
                    "end_time": dt.end_time.strftime("%H:%M"),
                    "reason": dt.reason
                }
                for dt in self.downtime_windows
            ],
            "operator_id": self.operator_id
        }
    
    def __str__(self) -> str:
        downtime_count = len(self.downtime_windows)
        return (f"Machine({self.machine_id}: {', '.join(self.capabilities)}, "
                f"{downtime_count} downtime window(s))")


@dataclass
class Constraint:
    """
    Represents scheduling constraints for the production system.
    
    This includes shift times, setup time matrices, priority weights, etc.
    """
    
    # Shift boundaries
    shift_start: time = time(8, 0)       # Shift starts at 08:00
    shift_end: time = time(16, 0)        # Shift ends at 16:00
    max_overtime_minutes: int = 0        # No overtime allowed by default
    
    # Setup times between product types (in minutes)
    # Example: {"P_A->P_A": 5, "P_A->P_B": 30, "P_B->P_B": 5, "P_B->P_A": 30}
    setup_times: Dict[str, int] = field(default_factory=dict)
    
    # Priority weights for rush vs normal jobs
    rush_job_weight: float = 10.0        # Rush jobs are 10x more important
    normal_job_weight: float = 1.0
    
    # Objective function weights
    tardiness_weight: float = 1.0        # How much we care about meeting deadlines
    setup_weight: float = 0.5            # How much we care about minimizing setups
    utilization_weight: float = 0.3      # How much we care about balancing load
    
    # WIP (Work in Progress) limits
    max_wip_per_machine: Optional[int] = None
    
    def get_setup_time(self, from_product: str, to_product: str) -> int:
        """
        Get setup time required when switching from one product to another.
        
        Args:
            from_product: Current product type
            to_product: Next product type
            
        Returns:
            Setup time in minutes
        """
        # If same product, use same-product setup time (usually shorter)
        if from_product == to_product:
            key = f"{from_product}->{to_product}"
            return self.setup_times.get(key, 5)  # Default 5 minutes
        
        # Different products require longer setup
        key = f"{from_product}->{to_product}"
        return self.setup_times.get(key, 30)  # Default 30 minutes
    
    def get_shift_duration_minutes(self) -> int:
        """
        Calculate total shift duration in minutes.
        
        Returns:
            Shift duration in minutes
        """
        start_minutes = self.shift_start.hour * 60 + self.shift_start.minute
        end_minutes = self.shift_end.hour * 60 + self.shift_end.minute
        return end_minutes - start_minutes
    
    def is_within_shift(self, time_point: time) -> bool:
        """
        Check if a time point falls within the shift.
        
        Args:
            time_point: Time to check
            
        Returns:
            True if within shift, False otherwise
        """
        point_minutes = time_point.hour * 60 + time_point.minute
        start_minutes = self.shift_start.hour * 60 + self.shift_start.minute
        end_minutes = self.shift_end.hour * 60 + self.shift_end.minute + self.max_overtime_minutes
        
        return start_minutes <= point_minutes <= end_minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert constraints to dictionary."""
        return {
            "shift_start": self.shift_start.strftime("%H:%M"),
            "shift_end": self.shift_end.strftime("%H:%M"),
            "max_overtime_minutes": self.max_overtime_minutes,
            "setup_times": self.setup_times,
            "rush_job_weight": self.rush_job_weight,
            "normal_job_weight": self.normal_job_weight,
            "tardiness_weight": self.tardiness_weight,
            "setup_weight": self.setup_weight,
            "utilization_weight": self.utilization_weight,
            "max_wip_per_machine": self.max_wip_per_machine
        }
    
    def __str__(self) -> str:
        return (f"Constraint(Shift: {self.shift_start}-{self.shift_end}, "
                f"{len(self.setup_times)} setup rules)")


# Example usage
if __name__ == "__main__":
    # Create a machine with downtime
    machine = Machine(
        machine_id="M1",
        capabilities=["P_A", "P_B"],
        capacity_per_hour=60,
        downtime_windows=[
            DowntimeWindow(time(10, 0), time(11, 30), "Scheduled Maintenance")
        ]
    )
    
    print(machine)
    print(f"Can produce P_A? {machine.can_produce('P_A')}")
    print(f"Available at 09:00? {machine.is_available_at(time(9, 0))}")
    print(f"Available at 10:30? {machine.is_available_at(time(10, 30))}")
    
    # Create constraints
    constraints = Constraint(
        shift_start=time(8, 0),
        shift_end=time(16, 0),
        setup_times={
            "P_A->P_A": 5,
            "P_A->P_B": 30,
            "P_B->P_A": 30,
            "P_B->P_B": 5
        }
    )
    
    print(f"\n{constraints}")
    print(f"Setup time P_A->P_B: {constraints.get_setup_time('P_A', 'P_B')} min")
    print(f"Shift duration: {constraints.get_shift_duration_minutes()} min")
