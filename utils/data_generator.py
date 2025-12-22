"""
Test Data Generator - Create realistic job scenarios for testing

This module provides functions to generate test data including:
- Randomly generated jobs
- Rush order scenarios
- Machine downtime events
- Complete test scenarios for demonstration
"""

import random
from datetime import time, datetime, timedelta
from typing import List, Optional
import pandas as pd
from pathlib import Path

from models.job import Job
from models.machine import Machine, DowntimeWindow


# Product type configurations
PRODUCT_TYPES = {
    'P_A': {'avg_time': 45, 'variance': 15},  # Average 45min, ±15min variance
    'P_B': {'avg_time': 60, 'variance': 20},
    'P_C': {'avg_time': 30, 'variance': 10},
}


def generate_random_jobs(
    num_jobs: int,
    machines: List[str] = None,
    rush_probability: float = 0.2,
    shift_start: time = time(8, 0),
    shift_end: time = time(16, 0)
) -> List[Job]:
    """
    Generate random production jobs for testing.
    
    Args:
        num_jobs: Number of jobs to generate
        machines: List of available machine IDs
        rush_probability: Probability (0-1) that a job is rush priority
        shift_start: Start of shift
        shift_end: End of shift
        
    Returns:
        List of Job objects
    """
    if machines is None:
        machines = ['M1', 'M2', 'M3']
    
    jobs = []
    shift_start_minutes = shift_start.hour * 60 + shift_start.minute
    shift_end_minutes = shift_end.hour * 60 + shift_end.minute
    
    for i in range(num_jobs):
        job_id = f"J{i+1:03d}"  # J001, J002, etc.
        
        # Random product type
        product_type = random.choice(list(PRODUCT_TYPES.keys()))
        config = PRODUCT_TYPES[product_type]
        
        # Random processing time
        processing_time = config['avg_time'] + random.randint(-config['variance'], config['variance'])
        processing_time = max(10, processing_time)  # Minimum 10 minutes
        
        # Random due time within shift
        due_minutes = random.randint(shift_start_minutes + 60, shift_end_minutes)
        due_time = time(due_minutes // 60, due_minutes % 60)
        
        # Random priority
        priority = "rush" if random.random() < rush_probability else "normal"
        
        # Random machine compatibility (1-3 machines)
        num_compatible = random.randint(1, len(machines))
        machine_options = random.sample(machines, num_compatible)
        
        job = Job(
            job_id=job_id,
            product_type=product_type,
            processing_time=processing_time,
            due_time=due_time,
            priority=priority,
            machine_options=machine_options
        )
        jobs.append(job)
    
    return jobs


def generate_rush_order() -> Job:
    """
    Generate a single rush order with tight deadline.
    
    Returns:
        Rush Job object
    """
    job_id = f"RUSH_{random.randint(1000, 9999)}"
    product_type = random.choice(list(PRODUCT_TYPES.keys()))
    config = PRODUCT_TYPES[product_type]
    
    processing_time = config['avg_time']
    
    # Rush order due in 2-3 hours from shift start
    current_hour = 8 + random.randint(2, 3)
    due_time = time(current_hour, random.choice([0, 15, 30, 45]))
    
    return Job(
        job_id=job_id,
        product_type=product_type,
        processing_time=processing_time,
        due_time=due_time,
        priority="rush",
        machine_options=['M1', 'M2', 'M3']  # Can run on any machine
    )


def generate_machine_downtime() -> DowntimeWindow:
    """
    Generate random machine downtime event.
    
    Returns:
        DowntimeWindow object
    """
    # Random downtime during shift (9am - 3pm)
    start_hour = random.randint(9, 14)
    start_minute = random.choice([0, 30])
    
    # Downtime lasts 30-90 minutes
    duration = random.randint(30, 90)
    
    start = time(start_hour, start_minute)
    end_minutes = start_hour * 60 + start_minute + duration
    end = time(end_minutes // 60, end_minutes % 60)
    
    reasons = [
        "Scheduled Maintenance",
        "Tool Change",
        "Quality Inspection",
        "Unplanned Breakdown",
        "Material Shortage"
    ]
    reason = random.choice(reasons)
    
    return DowntimeWindow(start, end, reason)


def create_test_scenario_1() -> dict[str, any]:
    """
    Test Scenario 1: Rush Order Insertion
    
    10 normal jobs + 2 rush orders
    """
    normal_jobs = generate_random_jobs(10, rush_probability=0.0)
    rush_jobs = [generate_rush_order() for _ in range(2)]
    
    all_jobs = normal_jobs + rush_jobs
    
    return {
        'name': 'Rush Order Insertion',
        'description': 'Test how optimizer handles inserting rush orders into existing schedule',
        'jobs': all_jobs,
        'num_normal': len(normal_jobs),
        'num_rush': len(rush_jobs)
    }


def create_test_scenario_2() -> dict[str, any]:
    """
    Test Scenario 2: Machine Downtime
    
    15 jobs with M2 experiencing downtime
    """
    jobs = generate_random_jobs(15, rush_probability=0.1)
    
    # M2 has downtime
    downtime = DowntimeWindow(time(10, 0), time(11, 30), "Scheduled Maintenance")
    
    return {
        'name': 'Machine Downtime',
        'description': 'Test rescheduling around M2 downtime 10:00-11:30',
        'jobs': jobs,
        'downtime': {'M2': downtime}
    }


def create_test_scenario_3() -> dict[str, any]:
    """
    Test Scenario 3: Setup Minimization
    
    Mixed product types to test batching
    """
    # Create specific mix: 6 P_A, 6 P_B, 3 P_C
    jobs = []
    job_num = 1
    
    for product_type, count in [('P_A', 6), ('P_B', 6), ('P_C', 3)]:
        for _ in range(count):
            config = PRODUCT_TYPES[product_type]
            jobs.append(Job(
                job_id=f"J{job_num:03d}",
                product_type=product_type,
                processing_time=config['avg_time'],
                due_time=time(15, 0),  # All due at 3pm
                priority="normal",
                machine_options=['M1', 'M2']
            ))
            job_num += 1
    
    # Shuffle to test if batching agent can regroup them
    random.shuffle(jobs)
    
    return {
        'name': 'Setup Minimization',
        'description': 'Test batching agent performance with mixed product types',
        'jobs': jobs,
        'expected_improvement': 'Should group by product type to minimize setups'
    }


def export_jobs_to_csv(jobs: List[Job], output_path: str):
    """
    Export jobs to CSV file for import into dashboard.
    
    Args:
        jobs: List of Job objects
        output_path: Path to save CSV
    """
    data = []
    for job in jobs:
        data.append({
            'job_id': job.job_id,
            'product_type': job.product_type,
            'processing_time': job.processing_time,
            'due_time': job.due_time.strftime('%H:%M'),
            'priority': job.priority,
            'machine_options': ','.join(job.machine_options)
        })
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Exported {len(jobs)} jobs to {output_path}")


# Example usage and CLI
if __name__ == "__main__":
    print("="*60)
    print("TEST DATA GENERATOR")
    print("="*60)
    
    # Generate and export scenario 1
    scenario1 = create_test_scenario_1()
    print(f"\n{scenario1['name']}")
    print(f"{scenario1['description']}")
    print(f"Total jobs: {len(scenario1['jobs'])} ({scenario1['num_normal']} normal, {scenario1['num_rush']} rush)")
    
    output_dir = Path(__file__).parent.parent / 'data'
    output_dir.mkdir(exist_ok=True)
    
    export_jobs_to_csv(scenario1['jobs'], str(output_dir / 'scenario1_rush_orders.csv'))
    
    # Generate and export scenario 2
    scenario2 = create_test_scenario_2()
    print(f"\n{scenario2['name']}")
    print(f"{scenario2['description']}")
    print(f"Total jobs: {len(scenario2['jobs'])}")
    
    export_jobs_to_csv(scenario2['jobs'], str(output_dir / 'scenario2_downtime.csv'))
    
    # Generate and export scenario 3
    scenario3 = create_test_scenario_3()
    print(f"\n{scenario3['name']}")
    print(f"{scenario3['description']}")
    print(f"Total jobs: {len(scenario3['jobs'])}")
    print(f"Expected: {scenario3['expected_improvement']}")
    
    export_jobs_to_csv(scenario3['jobs'], str(output_dir / 'scenario3_setup_minimization.csv'))
    
    print(f"\n✓ All test scenarios exported to {output_dir}")
