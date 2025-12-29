"""
Baseline Scheduler - Simple FIFO Implementation

This provides a baseline for comparison against the multi-agent optimizer.
Uses simple First-In-First-Out (FIFO) assignment with minimal intelligence.

Purpose: Show the improvement achieved by the AI-powered optimizer.
"""

import os
from datetime import time
from typing import List, Tuple
from collections import defaultdict

from models.job import Job
from models.machine import Machine, Constraint
from models.schedule import Schedule, JobAssignment


class BaselineScheduler:
    """
    Simple FIFO (First-In-First-Out) baseline scheduler.
    
    This scheduler uses minimal intelligence:
    - Assigns jobs in the order they appear
    - Chooses first available compatible machine
    - No optimization for setup time
    - No load balancing
    - Basic constraint checking
    
    Used as a baseline to demonstrate the improvement 
    achieved by the multi-agent optimizer.
    """
    
    def __init__(self):
        """Initialize baseline scheduler."""
        self.name = "Baseline FIFO Scheduler"
    
    def schedule(
        self,
        jobs: List[Job],
        machines: List[Machine],
        constraint: Constraint
    ) -> Tuple[Schedule, str]:
        """
        Create a simple FIFO schedule without optimization.
        
        Algorithm:
        1. Sort jobs by priority (rush first), then by order received
        2. For each job, find first compatible machine
        3. Assign job to machine at earliest available time
        4. No batching, no load balancing, no setup optimization
        
        Args:
            jobs: List of jobs to schedule
            machines: List of available machines
            constraint: Scheduling constraints
            
        Returns:
            Tuple of (Schedule, explanation)
        """
        
        # Create schedule
        schedule = Schedule()
        
        # Sort: rush first, then by job_id (arrival order)
        sorted_jobs = sorted(jobs, key=lambda j: (0 if j.is_rush else 1, j.job_id))
        
        # Track current time and product on each machine
        current_time = {m.machine_id: constraint.shift_start for m in machines}
        current_product = {m.machine_id: None for m in machines}
        
        # Simple FIFO assignment
        jobs_assigned = 0
        jobs_skipped = 0
        
        for job in sorted_jobs:
            # Find first compatible machine (no load balancing!)
            compatible = [
                m for m in machines
                if m.can_produce(job.product_type) and job.can_run_on(m.machine_id)
            ]
            
            if not compatible:
                jobs_skipped += 1
                continue
            
            # Just take the first one (no intelligent choice)
            machine = compatible[0]
            machine_id = machine.machine_id
            
            # Calculate setup time (but don't optimize for it)
            prev_product = current_product[machine_id]
            if prev_product and prev_product != job.product_type:
                setup_time = constraint.get_setup_time(prev_product, job.product_type)
            elif prev_product == job.product_type:
                setup_time = constraint.get_setup_time(job.product_type, job.product_type)
            else:
                setup_time = 0
            
            # Calculate timing (no downtime avoidance)
            start = current_time[machine_id]
            start_minutes = start.hour * 60 + start.minute + setup_time
            end_minutes = start_minutes + job.processing_time
            
            # Simple time conversion (may exceed shift)
            proposed_start = time(min(start_minutes // 60, 23), start_minutes % 60)
            proposed_end = time(min(end_minutes // 60, 23), end_minutes % 60)
            
            # Create assignment (no validation!)
            assignment = JobAssignment(
                job=job,
                machine_id=machine_id,
                start_time=proposed_start,
                end_time=proposed_end,
                setup_time_before=setup_time
            )
            
            schedule.add_assignment(assignment)
            
            # Update tracking
            current_time[machine_id] = proposed_end
            current_product[machine_id] = job.product_type
            jobs_assigned += 1
        
        # Calculate KPIs for the schedule (machines first, then constraint)
        schedule.calculate_kpis(machines, constraint)
        
        # Generate explanation
        explanation = f"""BASELINE FIFO SCHEDULER - NO OPTIMIZATION

Algorithm Used:
- First-In-First-Out (FIFO) assignment
- No batching or setup optimization
- No load balancing across machines
- No downtime avoidance
- Minimal intelligence

Results:
- Jobs assigned: {jobs_assigned} / {len(jobs)}
- Jobs skipped: {jobs_skipped}
- Simple sequential assignment
- No AI or optimization applied

NOTE: This is intentionally naive scheduling used for comparison.
The multi-agent optimizer should show significant improvements!
"""
        
        schedule.explanation = explanation
        return schedule, explanation
    
    def __str__(self) -> str:
        return "BaselineScheduler(algorithm=FIFO, optimization=None)"


# Quick test
if __name__ == "__main__":
    from utils.data_generator import generate_random_jobs
    from utils.config_loader import load_config
    
    print("Testing Baseline FIFO Scheduler...")
    
    # Generate test data
    config = load_config()
    test_jobs = generate_random_jobs(10, rush_probability=0.3)
    
    # Run baseline
    baseline = BaselineScheduler()
    schedule, explanation = baseline.schedule(
        test_jobs,
        config['machines'],
        config['constraint']
    )
    
    print("\n" + explanation)
    print(f"\nKPIs: {schedule.kpis}")
    print(f"Total tardiness: {schedule.kpis.total_tardiness} min")
    print(f"Setup time: {schedule.kpis.total_setup_time} min")
