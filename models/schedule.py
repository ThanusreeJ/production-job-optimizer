"""
Schedule Model - Represents production schedules and KPIs

This module defines the Schedule class for representing complete production
schedules and the KPI class for evaluating schedule quality.

Key Features:
    - Machine-wise job assignments
    - Timeline calculations
    - KPI computation (tardiness, utilization, setup time)
    - Schedule validation and scoring
"""

from datetime import time, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from models.job import Job
from models.machine import Machine, Constraint


@dataclass
class JobAssignment:
    """
    Represents a job assigned to a specific machine with timing.
    """
    job: Job
    machine_id: str
    start_time: time
    end_time: time
    setup_time_before: int = 0  # Setup minutes before this job
    
    def get_duration_minutes(self) -> int:
        """Calculate total duration including setup."""
        return self.job.processing_time + self.setup_time_before
    
    def is_late(self) -> bool:
        """Check if job finishes after its due time."""
        return self.end_time > self.job.due_time
    
    def get_tardiness_minutes(self) -> int:
        """Calculate how many minutes late this job is."""
        if not self.is_late():
            return 0
        
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        due_minutes = self.job.due_time.hour * 60 + self.job.due_time.minute
        return max(0, end_minutes - due_minutes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job.job_id,
            "product_type": self.job.product_type,
            "machine_id": self.machine_id,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "setup_time_before": self.setup_time_before,
            "processing_time": self.job.processing_time,
            "is_late": self.is_late(),
            "tardiness_minutes": self.get_tardiness_minutes()
        }


@dataclass
class KPI:
    """
    Key Performance Indicators for schedule evaluation.
    
    Lower scores are better (minimization objectives).
    """
    
    total_tardiness: int = 0              # Total minutes all jobs are late
    total_setup_time: int = 0             # Total setup time across all machines
    num_setup_switches: int = 0           # Number of product type changes
    max_machine_utilization: float = 0.0  # % utilization of busiest machine
    min_machine_utilization: float = 0.0  # % utilization of least busy machine
    utilization_imbalance: float = 0.0    # Difference between max and min
    num_violations: int = 0               # Constraint violations
    
    def get_weighted_score(self, constraint: Constraint) -> float:
        """
        Calculate weighted score based on constraint preferences.
        
        Lower is better.
        
        Args:
            constraint: Constraint object with weight preferences
            
        Returns:
            Weighted score
        """
        score = (
            self.total_tardiness * constraint.tardiness_weight +
            self.total_setup_time * constraint.setup_weight +
            self.utilization_imbalance * constraint.utilization_weight +
            self.num_violations * 1000  # Heavy penalty for violations
        )
        return score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tardiness": self.total_tardiness,
            "total_setup_time": self.total_setup_time,
            "num_setup_switches": self.num_setup_switches,
            "max_machine_utilization": round(self.max_machine_utilization, 2),
            "min_machine_utilization": round(self.min_machine_utilization, 2),
            "utilization_imbalance": round(self.utilization_imbalance, 2),
            "num_violations": self.num_violations
        }
    
    def __str__(self) -> str:
        return (f"KPI(Tardiness: {self.total_tardiness}min, "
                f"Setup: {self.total_setup_time}min, "
                f"Switches: {self.num_setup_switches}, "
                f"Violations: {self.num_violations})")


@dataclass
class Schedule:
    """
    Represents a complete production schedule.
    
    Contains machine-wise job assignments and calculated KPIs.
    """
    
    # Machine ID -> List of job assignments
    assignments: Dict[str, List[JobAssignment]] = field(default_factory=dict)
    
    # Calculated KPIs
    kpis: Optional[KPI] = None
    
    # Metadata
    created_by: str = "Multi-Agent Optimizer"
    explanation: str = ""  # LLM-generated explanation
    
    def add_assignment(self, assignment: JobAssignment):
        """
        Add a job assignment to the schedule.
        
        Args:
            assignment: JobAssignment to add
        """
        machine_id = assignment.machine_id
        if machine_id not in self.assignments:
            self.assignments[machine_id] = []
        
        self.assignments[machine_id].append(assignment)
    
    def get_machine_jobs(self, machine_id: str) -> List[JobAssignment]:
        """
        Get all jobs assigned to a specific machine.
        
        Args:
            machine_id: Machine identifier
            
        Returns:
            List of job assignments for that machine
        """
        return self.assignments.get(machine_id, [])
    
    def get_all_jobs(self) -> List[JobAssignment]:
        """Get all job assignments across all machines."""
        all_jobs = []
        for machine_jobs in self.assignments.values():
            all_jobs.extend(machine_jobs)
        return all_jobs
    
    def calculate_kpis(self, machines: List[Machine], constraint: Constraint) -> KPI:
        """
        Calculate KPIs for this schedule.
        
        Args:
            machines: List of all machines
            constraint: Scheduling constraints
            
        Returns:
            KPI object with calculated metrics
        """
        kpi = KPI()
        
        # Calculate tardiness
        all_jobs = self.get_all_jobs()
        kpi.total_tardiness = sum(job.get_tardiness_minutes() for job in all_jobs)
        
        # Calculate setup times and switches
        kpi.total_setup_time = sum(job.setup_time_before for job in all_jobs)
        
        # Count product type switches per machine
        for machine_id, jobs in self.assignments.items():
            if len(jobs) > 1:
                for i in range(1, len(jobs)):
                    if jobs[i].job.product_type != jobs[i-1].job.product_type:
                        kpi.num_setup_switches += 1
        
        # Calculate machine utilization
        shift_duration = constraint.get_shift_duration_minutes()
        utilizations = []
        
        for machine in machines:
            machine_jobs = self.get_machine_jobs(machine.machine_id)
            if machine_jobs:
                total_time = sum(job.get_duration_minutes() for job in machine_jobs)
                utilization = (total_time / shift_duration) * 100
                utilizations.append(utilization)
        
        if utilizations:
            kpi.max_machine_utilization = max(utilizations)
            kpi.min_machine_utilization = min(utilizations)
            kpi.utilization_imbalance = kpi.max_machine_utilization - kpi.min_machine_utilization
        
        self.kpis = kpi
        return kpi
    
    def validate(self, machines: List[Machine], constraint: Constraint) -> Tuple[bool, List[str]]:
        """
        Validate schedule against constraints.
        
        Args:
            machines: List of all machines
            constraint: Scheduling constraints
            
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        # Check each assignment
        for machine_id, jobs in self.assignments.items():
            for job_assignment in jobs:
                # Check shift boundaries
                if not constraint.is_within_shift(job_assignment.end_time):
                    violations.append(
                        f"Job {job_assignment.job.job_id} on {machine_id} "
                        f"ends at {job_assignment.end_time} (beyond shift)"
                    )
                
                # Check machine downtime
                machine = next((m for m in machines if m.machine_id == machine_id), None)
                if machine:
                    for downtime in machine.downtime_windows:
                        if downtime.overlaps_with(job_assignment.start_time, job_assignment.end_time):
                            violations.append(
                                f"Job {job_assignment.job.job_id} on {machine_id} "
                                f"overlaps with downtime {downtime}"
                            )
        
        # Update KPI with violation count
        if self.kpis:
            self.kpis.num_violations = len(violations)
        
        return len(violations) == 0, violations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary."""
        return {
            "assignments": {
                machine_id: [job.to_dict() for job in jobs]
                for machine_id, jobs in self.assignments.items()
            },
            "kpis": self.kpis.to_dict() if self.kpis else None,
            "created_by": self.created_by,
            "explanation": self.explanation
        }
    
    def __str__(self) -> str:
        total_jobs = sum(len(jobs) for jobs in self.assignments.values())
        return (f"Schedule({len(self.assignments)} machines, "
                f"{total_jobs} jobs, KPI: {self.kpis})")


# Example usage
if __name__ == "__main__":
    from models.job import Job
    from models.machine import Machine, Constraint
    
    # Create sample jobs
    job1 = Job("J001", "P_A", 45, time(12, 0), "rush", ["M1", "M2"])
    job2 = Job("J002", "P_A", 30, time(14, 0), "normal", ["M1", "M2"])
    job3 = Job("J003", "P_B", 60, time(15, 0), "normal", ["M1"])
    
    # Create schedule
    schedule = Schedule()
    
    # Add assignments
    schedule.add_assignment(JobAssignment(job1, "M1", time(8, 0), time(8, 45), 0))
    schedule.add_assignment(JobAssignment(job2, "M1", time(8, 50), time(9, 20), 5))
    schedule.add_assignment(JobAssignment(job3, "M2", time(8, 0), time(9, 30), 30))
    
    print(schedule)
    
    # Calculate KPIs
    machines = [Machine("M1", ["P_A", "P_B"]), Machine("M2", ["P_A", "P_B"])]
    constraint = Constraint()
    kpis = schedule.calculate_kpis(machines, constraint)
    
    print(f"\nKPIs: {kpis}")
    print(f"Weighted Score: {kpis.get_weighted_score(constraint)}")
    
    # Validate
    is_valid, violations = schedule.validate(machines, constraint)
    print(f"\nValid: {is_valid}")
    if violations:
        print("Violations:")
        for v in violations:
            print(f"  - {v}")
