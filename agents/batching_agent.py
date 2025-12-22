"""
Batching & Setup Minimization Agent

This agent specializes in grouping jobs by product type and minimizing
setup transitions to reduce changeover time and increase efficiency.

Key Responsibilities:
    - Group jobs by product family
    - Minimize setup frequency between different product types
    - Suggest optimized job sequences per machine
    - Calculate setup time savings

Uses Groq's llama-3.3-70b-versatile for fast optimization decisions.
"""

import os
from typing import List, Dict, Any, Tuple
from datetime import time, datetime, timedelta
from collections import defaultdict

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage


from models.job import Job
from models.machine import Machine, Constraint
from models.schedule import Schedule, JobAssignment


class BatchingAgent:
    """
    Agent responsible for batching similar jobs and minimizing setup time.
    
    This agent uses LLM reasoning to group jobs intelligently and minimize
    product type transitions that require lengthy setup operations.
    """
    
    def __init__(self, groq_api_key: str = None):
        """
        Initialize the Batching Agent with Groq LLM.
        
        Args:
            groq_api_key: Groq API key (if not provided, reads from environment)
        """
        if groq_api_key is None:
            groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not groq_api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable.")
        
        # Initialize Groq LLM
        # Using llama-3.3-70b-versatile for fast inference
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model_name=os.getenv('GROQ_MODEL_AGENTS', 'llama-3.3-70b-versatile'),
            temperature=0.1,  # Low temperature for consistent optimization
            max_tokens=2048
        )
        
        # System prompt for batching agent
        self.system_prompt = """You are a Batching & Setup Minimization Agent in a production scheduling system.

Your ONLY job is to:
1. Group jobs by product type to minimize setup changes
2. Suggest optimal job sequences that reduce setup time
3. Balance between batching efficiency and meeting deadlines

IMPORTANT RULES:
- Rush jobs (priority='rush') must be prioritized even if they break batching
- Consider setup times between product types
- Aim to minimize total setup time while respecting priorities

You will receive job data and setup time information.
Respond with concise recommendations on how to batch and sequence jobs."""
    
    def analyze_jobs(self, jobs: List[Job], constraint: Constraint) -> str:
        """
        Analyze jobs and provide batching recommendations using LLM.
        
        Args:
            jobs: List of jobs to analyze
            constraint: Scheduling constraints with setup times
            
        Returns:
            LLM-generated batching recommendations
        """
        # Prepare job summary
        job_summary = []
        for job in jobs:
            job_summary.append(
                f"- {job.job_id}: {job.product_type}, {job.processing_time}min, "
                f"due {job.due_time}, priority={job.priority}"
            )
        
        # Prepare setup time info
        setup_info = []
        for key, value in constraint.setup_times.items():
            setup_info.append(f"  {key}: {value} min")
        
        # Create prompt
        prompt = f"""Analyze the following jobs for optimal batching:

JOBS:
{chr(10).join(job_summary)}

SETUP TIMES:
{chr(10).join(setup_info)}

Provide a concise batching strategy that:
1. Groups similar product types together
2. Prioritizes rush jobs
3. Minimizes total setup time

Format your response as specific recommendations."""
        
        # Get LLM response
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def create_batched_schedule(
        self,
        jobs: List[Job],
        machines: List[Machine],
        constraint: Constraint
    ) -> Tuple[Schedule, str]:
        """
        Create a schedule optimized for minimal setup time.
        
        This method:
        1. Groups jobs by product type
        2. Places rush jobs first in their product groups
        3. Sequences jobs to minimize setup transitions
        4. Distributes batches across available machines
        5. SKIPS DOWNTIME WINDOWS
        
        Args:
            jobs: List of jobs to schedule
            machines: List of available machines
            constraint: Scheduling constraints
            
        Returns:
            Tuple of (Schedule, explanation)
        """
        # Get LLM recommendations
        llm_recommendations = self.analyze_jobs(jobs, constraint)
        
        # Group jobs by product type
        product_groups = defaultdict(list)
        for job in jobs:
            product_groups[job.product_type].append(job)
        
        # Within each group, prioritize rush jobs
        for product_type in product_groups:
            product_groups[product_type].sort(
                key=lambda j: (0 if j.is_rush else 1, j.due_time)
            )
        
        # Create schedule
        schedule = Schedule()
        current_time = {m.machine_id: constraint.shift_start for m in machines}
        current_product = {m.machine_id: None for m in machines}
        
        # Distribute product groups across machines to balance load
        machine_loads = {m.machine_id: 0 for m in machines}
        
        # Flatten jobs while preserving priority (rush first, then by product group)
        all_jobs_sorted = []
        for product_type, group_jobs in product_groups.items():
            all_jobs_sorted.extend(group_jobs)
        
        for job in all_jobs_sorted:
            # Find best machine (compatible and least loaded)
            compatible_machines = [
                m for m in machines
                if m.can_produce(job.product_type) and job.can_run_on(m.machine_id)
            ]
            
            if not compatible_machines:
                continue
            
            # Try machines in order of lowest load
            compatible_machines.sort(key=lambda m: machine_loads[m.machine_id])
            
            assigned = False
            for best_machine in compatible_machines:
                machine_id = best_machine.machine_id
                
                # Calculate setup time
                prev_product = current_product[machine_id]
                if prev_product and prev_product != job.product_type:
                    setup_time = constraint.get_setup_time(prev_product, job.product_type)
                elif prev_product == job.product_type:
                    setup_time = constraint.get_setup_time(job.product_type, job.product_type)
                else:
                    setup_time = 0  # First job on machine
                
                # Calculate proposed start and end times
                start = current_time[machine_id]
                start_minutes = start.hour * 60 + start.minute + setup_time
                end_minutes = start_minutes + job.processing_time
                
                # Check if this time range overlaps with any downtime
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
                    # Try again with updated time after downtime
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
                
                schedule.add_assignment(assignment)
                
                # Update tracking
                current_time[machine_id] = proposed_end
                current_product[machine_id] = job.product_type
                machine_loads[machine_id] += job.processing_time + setup_time
                
                assigned = True
                break  # Successfully assigned, move to next job
        
        # Generate explanation
        explanation = f"""BATCHING AGENT RECOMMENDATIONS:
{llm_recommendations}

IMPLEMENTATION:
- Grouped {len(product_groups)} product types
- Prioritized {sum(1 for j in jobs if j.is_rush)} rush jobs
- Distributed across {len(machines)} machines
- Sequenced jobs to minimize setup transitions
- Avoided machine downtime windows

RESULT:
- Total jobs scheduled: {len(schedule.get_all_jobs())} / {len(jobs)}
- Product batching applied to reduce changeover time
"""
        
        schedule.explanation = explanation
        return schedule, explanation
    
    def __str__(self) -> str:
        return "BatchingAgent(model=llama-3.3-70b-versatile)"


# Example usage
if __name__ == "__main__":
    from models.job import Job
    from models.machine import Machine, Constraint
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Create test jobs
    jobs = [
        Job("J001", "P_A", 45, time(12, 0), "rush", ["M1", "M2"]),
        Job("J002", "P_A", 30, time(14, 0), "normal", ["M1", "M2"]),
        Job("J003", "P_B", 60, time(15, 0), "normal", ["M1"]),
        Job("J004", "P_A", 40, time(13, 0), "normal", ["M2"]),
    ]
    
    # Create machines
    machines = [
        Machine("M1", ["P_A", "P_B"]),
        Machine("M2", ["P_A", "P_B"])
    ]
    
    # Create constraints
    constraint = Constraint(
        setup_times={
            "P_A->P_A": 5,
            "P_A->P_B": 30,
            "P_B->P_A": 30,
            "P_B->P_B": 5
        }
    )
    
    # Test batching agent
    agent = BatchingAgent()
    schedule, explanation = agent.create_batched_schedule(jobs, machines, constraint)
    
    print(schedule)
    print(f"\n{explanation}")
