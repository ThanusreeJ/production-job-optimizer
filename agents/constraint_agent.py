"""
Constraint & Policy Agent

This agent validates schedules against all operational constraints and
business rules to ensure feasibility and compliance.

Key Responsibilities:
    - Validate shift boundary compliance
    - Check machine downtime conflicts
    - Enforce rush order priority rules
    - Verify setup time constraints
    - Read and apply policies from configuration
    - Return violation reports or approval

Does NOT use LLM - uses deterministic rule checking for reliability.
"""

import os
from typing import List, Dict, Any, Tuple
from datetime import time

from models.job import Job
from models.machine import Machine, Constraint
from models.schedule import Schedule, JobAssignment


class ConstraintAgent:
    """
    Agent responsible for validating schedules against all constraints.
    
    This agent performs deterministic rule checking to ensure schedules
    are feasible and compliant with all operational constraints.
    """
    
    def __init__(self):
        """Initialize the Constraint & Policy Agent."""
        pass
    
    def validate_schedule(
        self,
        schedule: Schedule,
        jobs: List[Job],
        machines: List[Machine],
        constraint: Constraint
    ) -> Tuple[bool, List[str], str]:
        """
        Comprehensive validation of a schedule against all constraints.
        
        Args:
            schedule: Schedule to validate
            jobs: Original list of all jobs
            machines: List of machines
            constraint: Constraint rules
            
        Returns:
            Tuple of (is_valid, violations, report)
        """
        violations = []
        
        # 1. Check that all jobs are assigned
        assigned_job_ids = {assignment.job.job_id for assignment in schedule.get_all_jobs()}
        all_job_ids = {job.job_id for job in jobs}
        missing_jobs = all_job_ids - assigned_job_ids
        
        if missing_jobs:
            violations.append(f"Not all jobs assigned. Missing: {', '.join(missing_jobs)}")
        
        # 2. Validate each job assignment
        for assignment in schedule.get_all_jobs():
            # Check shift boundaries
            end_minutes = assignment.end_time.hour * 60 + assignment.end_time.minute
            shift_end_minutes = constraint.shift_end.hour * 60 + constraint.shift_end.minute
            shift_end_with_overtime = shift_end_minutes + constraint.max_overtime_minutes
            
            if end_minutes > shift_end_with_overtime:
                violations.append(
                    f"Job {assignment.job.job_id} on {assignment.machine_id} ends at "
                    f"{assignment.end_time} (exceeds shift end + overtime)"
                )
            
            # Check machine compatibility
            machine = next((m for m in machines if m.machine_id == assignment.machine_id), None)
            if machine:
                if not machine.can_produce(assignment.job.product_type):
                    violations.append(
                        f"Machine {assignment.machine_id} cannot produce "
                        f"{assignment.job.product_type} (Job {assignment.job.job_id})"
                    )
                
                # Check downtime conflicts
                for downtime in machine.downtime_windows:
                    if downtime.overlaps_with(assignment.start_time, assignment.end_time):
                        violations.append(
                            f"Job {assignment.job.job_id} on {assignment.machine_id} "
                            f"overlaps with downtime: {downtime}"
                        )
        
        # 3. Check for time overlaps on same machine
        machine_timelines = {}
        for assignment in schedule.get_all_jobs():
            machine_id = assignment.machine_id
            if machine_id not in machine_timelines:
                machine_timelines[machine_id] = []
            
            start_min = assignment.start_time.hour * 60 + assignment.start_time.minute
            end_min = assignment.end_time.hour * 60 + assignment.end_time.minute
            
            # Check against existing assignments on this machine
            for existing_start, existing_end, existing_job in machine_timelines[machine_id]:
                # Check for overlap
                if not (end_min <= existing_start or start_min >= existing_end):
                    violations.append(
                        f"Time overlap on {machine_id}: Jobs {assignment.job.job_id} "
                        f"and {existing_job} conflict"
                    )
            
            machine_timelines[machine_id].append((start_min, end_min, assignment.job.job_id))
        
        # 4. Check rush job deadlines (critical)
        rush_violations = []
        for assignment in schedule.get_all_jobs():
            if assignment.job.is_rush and assignment.is_late():
                tardiness = assignment.get_tardiness_minutes()
                rush_violations.append(
                    f"CRITICAL: Rush job {assignment.job.job_id} is {tardiness} min late "
                    f"(due {assignment.job.due_time}, ends {assignment.end_time})"
                )
        
        violations.extend(rush_violations)
        
        # 5. Generate validation report
        is_valid = len(violations) == 0
        
        if is_valid:
            report = f"""CONSTRAINT VALIDATION: ✓ PASSED

All {len(schedule.get_all_jobs())} job assignments validated successfully.

Checks Performed:
✓ All jobs assigned to machines
✓ Shift boundaries respected
✓ No machine downtime conflicts
✓ Machine-product compatibility verified
✓ No time overlaps on same machine
✓ Rush job deadlines met

Schedule is VALID and ready for execution."""
        else:
            report = f"""CONSTRAINT VALIDATION: ✗ FAILED

Found {len(violations)} violation(s):

"""
            for i, violation in enumerate(violations, 1):
                report += f"{i}. {violation}\n"
            
            report += f"""
This schedule CANNOT be executed. Optimization must retry with corrections."""
        
        return is_valid, violations, report
    
    def check_rush_job_priority(
        self,
        schedule: Schedule,
        constraint: Constraint
    ) -> Tuple[int, str]:
        """
        Check if rush jobs are properly prioritized.
        
        Args:
            schedule: Schedule to check
            constraint: Constraint with priority weights
            
        Returns:
            Tuple of (num_rush_violations, report)
        """
        violations = 0
        details = []
        
        for assignment in schedule.get_all_jobs():
            if assignment.job.is_rush:
                if assignment.is_late():
                    violations += 1
                    details.append(
                        f"Rush job {assignment.job.job_id} misses deadline by "
                        f"{assignment.get_tardiness_minutes()} minutes"
                    )
        
        if violations == 0:
            report = "✓ All rush jobs meet their deadlines"
        else:
            report = f"✗ {violations} rush job(s) miss deadlines:\n" + "\n".join(details)
        
        return violations, report
    
    def __str__(self) -> str:
        return "ConstraintAgent(rule-based validation)"


# Example usage
if __name__ == "__main__":
    from models.job import Job
    from models.machine import Machine, Constraint, DowntimeWindow
    from models.schedule import Schedule, JobAssignment
    
    # Create test scenario
    jobs = [
        Job("J001", "P_A", 45, time(12, 0), "rush", ["M1", "M2"]),
        Job("J002", "P_B", 60, time(14, 0), "normal", ["M1"]),
    ]
    
    machines = [
        Machine("M1", ["P_A", "P_B"], downtime_windows=[
            DowntimeWindow(time(10, 0), time(11, 0), "Maintenance")
        ]),
        Machine("M2", ["P_A"])
    ]
    
    constraint = Constraint()
    
    # Create VALID schedule
    valid_schedule = Schedule()
    valid_schedule.add_assignment(
        JobAssignment(jobs[0], "M1", time(8, 0), time(8, 45), 0)
    )
    valid_schedule.add_assignment(
        JobAssignment(jobs[1], "M1", time(11, 0), time(12, 0), 0)
    )
    
    # Test validation
    agent = ConstraintAgent()
    is_valid, violations, report = agent.validate_schedule(valid_schedule, jobs, machines, constraint)
    
    print(report)
    print(f"\nValid: {is_valid}")
    print(f"Violations: {len(violations)}")
