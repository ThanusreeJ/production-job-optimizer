"""
Bottleneck Relief Agent

This agent specializes in detecting and relieving bottlenecks by identifying
overloaded machines and redistributing work to underutilized machines.

Key Responsibilities:
    - Detect machines with excessive load or long queues
    - Identify underutilized machines
    - Re-route compatible jobs to balance workload
    - Improve overall utilization balance and reduce makespan

Uses Groq's llama-3.3-70b-versatile for load balancing decisions.
"""

import os
from typing import List, Dict, Any, Tuple
from datetime import time
from collections import defaultdict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from models.job import Job
from models.machine import Machine, Constraint
from models.schedule import Schedule, JobAssignment


class BottleneckAgent:
    """
    Agent responsible for detecting and relieving machine bottlenecks.
    
    This agent analyzes machine loads and redistributes jobs to achieve
    better balance and reduce overall completion time.
    """
    
    def __init__(self, groq_api_key: str = None):
        """
        Initialize the Bottleneck Relief Agent with Groq LLM.
        
        Args:
            groq_api_key: Groq API key (if not provided, reads from environment)
        """
        if groq_api_key is None:
            groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not groq_api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY environment variable.")
        
        # Initialize Groq LLM
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model_name=os.getenv('GROQ_MODEL_AGENTS', 'llama-3.3-70b-versatile'),
            temperature=0.1,
            max_tokens=2048
        )
        
        self.system_prompt = """You are a Bottleneck Relief Agent in a production scheduling system.

Your ONLY job is to:
1. Detect overloaded machines (bottlenecks)
2. Find underutilized machines
3. Suggest job redistributions to balance the load
4. Ensure job-machine compatibility when moving jobs

IMPORTANT RULES:
- Only suggest moving jobs that are compatible with the target machine
- Prioritize balancing utilization across all machines
- Consider both processing time and downtime

Respond with concise load balancing recommendations."""
    
    def analyze_load_distribution(
        self,
        schedule: Schedule,
        machines: List[Machine],
        constraint: Constraint
    ) -> str:
        """
        Analyze machine load distribution and provide recommendations.
        
        Args:
            schedule: Current schedule to analyze
            machines: List of all machines
            constraint: Scheduling constraints
            
        Returns:
            LLM-generated load balancing recommendations
        """
        # Calculate load per machine
        machine_loads = {}
        for machine in machines:
            jobs = schedule.get_machine_jobs(machine.machine_id)
            total_time = sum(job.get_duration_minutes() for job in jobs)
            machine_loads[machine.machine_id] = {
                'total_time': total_time,
                'num_jobs': len(jobs),
                'jobs': [j.job.job_id for j in jobs]
            }
        
        # Create summary for LLM
        load_summary = []
        for machine_id, load_info in machine_loads.items():
            load_summary.append(
                f"- {machine_id}: {load_info['total_time']} min total, "
                f"{load_info['num_jobs']} jobs: {', '.join(load_info['jobs'])}"
            )
        
        shift_duration = constraint.get_shift_duration_minutes()
        
        prompt = f"""Analyze machine load distribution for bottlenecks:

SHIFT DURATION: {shift_duration} minutes

MACHINE LOADS:
{chr(10).join(load_summary)}

Identify:
1. Which machine(s) are bottlenecks (overloaded)?
2. Which machine(s) are underutilized?
3. Which jobs could be moved to balance the load?

Provide specific recommendations."""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def rebalance_schedule(
        self,
        schedule: Schedule,
        machines: List[Machine],
        constraint: Constraint,
        all_jobs: List[Job]
    ) -> Tuple[Schedule, str]:
        """
        Create a rebalanced schedule that reduces bottlenecks.
        
        Args:
            schedule: Original schedule (may be from batching agent)
            machines: List of available machines
            constraint: Scheduling constraints
            all_jobs: Complete list of all jobs
            
        Returns:
            Tuple of (rebalanced Schedule, explanation)
        """
        # Get LLM analysis
        llm_analysis = self.analyze_load_distribution(schedule, machines, constraint)
        
        # Calculate current loads
        machine_loads = {m.machine_id: 0 for m in machines}
        for machine in machines:
            jobs = schedule.get_machine_jobs(machine.machine_id)
            machine_loads[machine.machine_id] = sum(
                job.get_duration_minutes() for job in jobs
            )
        
        # Identify bottleneck (most loaded) and underutilized machines
        max_load = max(machine_loads.values()) if machine_loads else 0
        min_load = min(machine_loads.values()) if machine_loads else 0
        avg_load = sum(machine_loads.values()) / len(machines) if machines else 0
        
        # Create new schedule with load balancing
        new_schedule = Schedule()
        remaining_jobs = all_jobs.copy()
        
        # Sort jobs by priority (rush first) then by processing time (longest first)
        remaining_jobs.sort(
            key=lambda j: (0 if j.is_rush else 1, -j.processing_time)
        )
        
        # Assign jobs using load-balancing strategy
        current_time = {m.machine_id: constraint.shift_start for m in machines}
        current_loads = {m.machine_id: 0 for m in machines}
        current_product = {m.machine_id: None for m in machines}
        
        for job in remaining_jobs:
            # Find compatible machines
            compatible = [
                m for m in machines
                if m.can_produce(job.product_type) and job.can_run_on(m.machine_id)
            ]
            
            if not compatible:
                continue
            
            # Sort by current load (lowest first)
            compatible.sort(key=lambda m: current_loads[m.machine_id])
            
            assigned = False
            for best_machine in compatible:
                machine_id = best_machine.machine_id
                
                # Calculate setup time
                prev_product = current_product[machine_id]
                if prev_product:
                    setup_time = constraint.get_setup_time(prev_product, job.product_type)
                else:
                    setup_time = 0
                
                # Calculate proposed timing
                start = current_time[machine_id]
                start_minutes = start.hour * 60 + start.minute + setup_time
                end_minutes = start_minutes + job.processing_time
                
                proposed_start = time(start_minutes // 60, start_minutes % 60)
                proposed_end = time(min(end_minutes // 60, 23), end_minutes % 60)
                
                # Check for downtime conflicts
                has_conflict = False
                for downtime in best_machine.downtime_windows:
                    if downtime.overlaps_with(proposed_start, proposed_end):
                        has_conflict = True
                        # Skip past the downtime
                        dt_end_minutes = downtime.end_time.hour * 60 + downtime.end_time.minute
                        current_time[machine_id] = time(dt_end_minutes // 60, dt_end_minutes % 60)
                        break
                
                if has_conflict:
                    # Try again after downtime
                    start = current_time[machine_id]
                    start_minutes = start.hour * 60 + start.minute + setup_time
                    end_minutes = start_minutes + job.processing_time
                    
                    proposed_start = time(start_minutes // 60, start_minutes % 60)
                    proposed_end = time(min(end_minutes // 60, 23), end_minutes % 60)
                    
                    # Check again
                    still_conflict = False
                    for downtime in best_machine.downtime_windows:
                        if downtime.overlaps_with(proposed_start, proposed_end):
                            still_conflict = True
                            break
                    
                    if still_conflict:
                        # Can't fit on this machine, try next one
                        continue
                
                # No conflict, create assignment
                assignment = JobAssignment(
                    job=job,
                    machine_id=machine_id,
                    start_time=proposed_start,
                    end_time=proposed_end,
                    setup_time_before=setup_time
                )
                
                new_schedule.add_assignment(assignment)
                
                # Update tracking
                current_time[machine_id] = proposed_end
                current_product[machine_id] = job.product_type
                current_loads[machine_id] += job.processing_time + setup_time
                
                assigned = True
                break  # Successfully assigned
        
        # Calculate improvement
        new_max_load = max(current_loads.values()) if current_loads else 0
        new_min_load = min(current_loads.values()) if current_loads else 0
        improvement = (max_load - min_load) - (new_max_load - new_min_load)
        
        # Generate explanation
        explanation = f"""BOTTLENECK AGENT ANALYSIS:
{llm_analysis}

LOAD BALANCING RESULTS:
Original Load Distribution:
- Max load: {max_load} min
- Min load: {min_load} min
- Imbalance: {max_load - min_load} min

Rebalanced Load Distribution:
- Max load: {new_max_load} min
- Min load: {new_min_load} min
- Imbalance: {new_max_load - new_min_load} min
- Improvement: {improvement} min reduction in imbalance

STRATEGY:
- Used load-aware assignment (always choose least-loaded compatible machine)
- Preserved rush job priority
- Avoided machine downtime windows
- Balanced {len(all_jobs)} jobs across {len(machines)} machines
- Successfully scheduled: {len(new_schedule.get_all_jobs())} / {len(all_jobs)} jobs
"""
        
        new_schedule.explanation = explanation
        return new_schedule, explanation
    
    def __str__(self) -> str:
        return "BottleneckAgent(model=llama-3.3-70b-versatile)"


# Example usage
if __name__ == "__main__":
    from models.job import Job
    from models.machine import Machine, Constraint
    from models.schedule import Schedule, JobAssignment
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Create heavily imbalanced schedule
    jobs = [
        Job("J001", "P_A", 60, time(12, 0), "normal", ["M1", "M2"]),
        Job("J002", "P_A", 45, time(13, 0), "normal", ["M1", "M2"]),
        Job("J003", "P_A", 50, time(14, 0), "normal", ["M1", "M2"]),
        Job("J004", "P_B", 30, time(15, 0), "normal", ["M2"]),
    ]
    
    machines = [
        Machine("M1", ["P_A"]),
        Machine("M2", ["P_A", "P_B"])
    ]
    
    constraint = Constraint()
    
    # Create imbalanced schedule (all on M2)
    imbalanced = Schedule()
    for job in jobs:
        imbalanced.add_assignment(
            JobAssignment(job, "M2", time(8, 0), time(9, 0), 0)
        )
    
    print("BEFORE BALANCING:")
    print(f"M1: {len(imbalanced.get_machine_jobs('M1'))} jobs")
    print(f"M2: {len(imbalanced.get_machine_jobs('M2'))} jobs")
    
    # Test bottleneck agent
    agent = BottleneckAgent()
    balanced, explanation = agent.rebalance_schedule(imbalanced, machines, constraint, jobs)
    
    print("\nAFTER BALANCING:")
    print(f"M1: {len(balanced.get_machine_jobs('M1'))} jobs")
    print(f"M2: {len(balanced.get_machine_jobs('M2'))} jobs")
    print(f"\n{explanation}")
