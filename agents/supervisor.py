"""
Supervisor Agent - Main Coordinator

This agent coordinates all other specialist agents and makes final decisions
on schedule selection based on KPI scores and business objectives.

Key Responsibilities:
    - Receive optimization requests
    - Delegate tasks to specialist agents
    - Consolidate candidate schedules
    - Score schedules using weighted KPIs
    - Select best schedule
    - Generate comprehensive explanation reports

Uses Groq's llama-3.3-70b-versatile (most powerful) for complex reasoning.
"""

import os
from typing import List, Dict, Any, Tuple
from datetime import time

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from models.job import Job
from models.machine import Machine, Constraint
from models.schedule import Schedule, KPI


class SupervisorAgent:
    """
    Supervisor Agent - The main coordinator of the multi-agent system.
    
    This agent orchestrates the optimization process by coordinating
    specialist agents and selecting the best schedule.
    """
    
    def __init__(self, groq_api_key: str = None):
        """
        Initialize the Supervisor Agent with Groq LLM.
        
        Args:
            groq_api_key: Groq API key (if not provided, reads from environment)
        """
        if groq_api_key is None:
            groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not groq_api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY environment variable.")
        
        # Initialize Groq LLM with most powerful model
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model_name=os.getenv('GROQ_MODEL_SUPERVISOR', 'llama-3.3-70b-versatile'),
            temperature=0.2,  # Slightly higher for creative reasoning
            max_tokens=4096   # Larger for detailed explanations
        )
        
        self.system_prompt = """You are the Supervisor Agent in a multi-agent production scheduling system.

Your role is to:
1. Coordinate specialist agents (Batching, Bottleneck, Constraint)
2. Evaluate candidate schedules based on KPIs
3. Make final selection decisions
4. Generate clear, professional explanations for planners

When analyzing schedules, consider:
- Total tardiness (meeting deadlines)
- Setup time and number of switches
- Machine utilization balance
- Constraint violations (MUST be zero)
- Rush job priority

Provide concise, executive-level explanations that non-technical plant managers can understand."""
    
    def analyze_optimization_request(
        self,
        jobs: List[Job],
        machines: List[Machine],
        constraint: Constraint
    ) -> str:
        """
        Analyze the optimization request and create a strategy.
        
        Args:
            jobs: List of jobs to schedule
            machines: Available machines
            constraint: Scheduling constraints
            
        Returns:
            LLM-generated optimization strategy
        """
        # Summarize request
        num_rush = sum(1 for j in jobs if j.is_rush)
        num_normal = len(jobs) - num_rush
        
        product_types = set(j.product_type for j in jobs)
        
        # Machine downtimes
        downtime_summary = []
        for machine in machines:
            if machine.downtime_windows:
                for dt in machine.downtime_windows:
                    downtime_summary.append(
                        f"  {machine.machine_id}: {dt.start_time}-{dt.end_time} ({dt.reason})"
                    )
        
        prompt = f"""Analyze this production scheduling request:

JOBS:
- Total: {len(jobs)} jobs
- Rush orders: {num_rush}
- Normal orders: {num_normal}
- Product types: {', '.join(product_types)}

MACHINES:
- Total: {len(machines)} machines
- Capabilities: {', '.join(m.machine_id + '=' + '+'.join(m.capabilities) for m in machines)}

DOWNTIMES:
{chr(10).join(downtime_summary) if downtime_summary else '  None scheduled'}

SHIFT:
- Duration: {constraint.shift_start} to {constraint.shift_end}

Based on this, what are the key optimization challenges and priorities?
Provide a brief strategic overview."""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def select_best_schedule(
        self,
        candidates: List[Tuple[Schedule, str]],
        constraint: Constraint
    ) -> Tuple[Schedule, str]:
        """
        Select the best schedule from multiple candidates.
        
        Args:
            candidates: List of (Schedule, source_description) tuples
            constraint: Constraint with scoring weights
            
        Returns:
            Tuple of (best_schedule, explanation)
        """
        if not candidates:
            raise ValueError("No candidate schedules provided")
        
        # Score each candidate
        scored_candidates = []
        for schedule, source in candidates:
            if schedule.kpis:
                score = schedule.kpis.get_weighted_score(constraint)
                scored_candidates.append((schedule, source, score, schedule.kpis))
        
        # Sort by score (lower is better)
        scored_candidates.sort(key=lambda x: x[2])
        
        # Get best schedule
        best_schedule, best_source, best_score, best_kpis = scored_candidates[0]
        
        # Prepare comparison summary for LLM
        comparison_lines = []
        for i, (sched, source, score, kpis) in enumerate(scored_candidates, 1):
            comparison_lines.append(
                f"{i}. {source}: Score={score:.1f}, Tardiness={kpis.total_tardiness}min, "
                f"Setup={kpis.total_setup_time}min, Balance={kpis.utilization_imbalance:.1f}%"
            )
        
        prompt = f"""Review the candidate schedules and explain why the selected one is best:

CANDIDATES (sorted by score, lower is better):
{chr(10).join(comparison_lines)}

SELECTED: {best_source} (Score: {best_score:.1f})

KPIs:
- Total Tardiness: {best_kpis.total_tardiness} minutes
- Setup Time: {best_kpis.total_setup_time} minutes ({best_kpis.num_setup_switches} switches)
- Utilization Balance: {best_kpis.utilization_imbalance:.1f}% imbalance
- Violations: {best_kpis.num_violations}

Write a brief executive summary explaining:
1. Why this schedule was selected
2. Key strengths
3. What trade-offs were made (if any)

Keep it concise and non-technical."""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Create comprehensive explanation
        full_explanation = f"""
╔════════════════════════════════════════════════════════════════╗
║     MULTI-AGENT OPTIMIZATION - FINAL RECOMMENDATION            ║
╚════════════════════════════════════════════════════════════════╝

{response.content}

═══════════════════════════════════════════════════════════════════
DETAILED KPI BREAKDOWN
═══════════════════════════════════════════════════════════════════

Schedule Quality Score: {best_score:.2f} (lower is better)

• Tardiness: {best_kpis.total_tardiness} minutes total delay
• Setup Efficiency: {best_kpis.total_setup_time} min, {best_kpis.num_setup_switches} product switches
• Load Balance: {best_kpis.max_machine_utilization:.1f}% max vs {best_kpis.min_machine_utilization:.1f}% min
  → Imbalance: {best_kpis.utilization_imbalance:.1f}%
• Constraint Compliance: {"✓ VALID" if best_kpis.num_violations == 0 else f"✗ {best_kpis.num_violations} violations"}

═══════════════════════════════════════════════════════════════════
OPTIMIZATION STRATEGY: {best_source}
═══════════════════════════════════════════════════════════════════

This schedule was proven superior against {len(candidates)} candidate schedules
generated by different optimization strategies.

Status: READY FOR EXECUTION
"""
        
        best_schedule.explanation = full_explanation
        return best_schedule, full_explanation
    
    def generate_executive_summary(
        self,
        schedule: Schedule,
        jobs: List[Job],
        machines: List[Machine],
        optimization_time_seconds: float
    ) -> str:
        """
        Generate a high-level executive summary for management.
        
        Args:
            schedule: Final optimized schedule
            jobs: Original job list
            machines: Machine list
            optimization_time_seconds: How long optimization took
            
        Returns:
            Executive summary text
        """
        num_jobs = len(schedule.get_all_jobs())
        num_rush = sum(1 for a in schedule.get_all_jobs() if a.job.is_rush)
        
        kpis = schedule.kpis
        
        prompt = f"""Generate a brief executive summary for plant management:

OPTIMIZATION RESULTS:
- {num_jobs} jobs scheduled across {len(machines)} machines
- {num_rush} rush orders included
- Optimization completed in {optimization_time_seconds:.1f} seconds

PERFORMANCE:
- {kpis.total_tardiness} minutes total tardiness
- {kpis.num_setup_switches} product changeovers
- {kpis.utilization_imbalance:.1f}% load imbalance between machines

Write 2-3 sentences suitable for a plant manager email.
Focus on business impact, not technical details."""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def __str__(self) -> str:
        return "SupervisorAgent(model=llama-3.3-70b-versatile)"


# Example usage
if __name__ == "__main__":
    from models.job import Job
    from models.machine import Machine, Constraint
    from models.schedule import Schedule, KPI
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Create test data
    jobs = [
        Job("J001", "P_A", 45, time(12, 0), "rush", ["M1", "M2"]),
        Job("J002", "P_A", 30, time(14, 0), "normal", ["M1", "M2"]),
    ]
    
    machines = [
        Machine("M1", ["P_A", "P_B"]),
        Machine("M2", ["P_A", "P_B"])
    ]
    
    constraint = Constraint()
    
    # Test supervisor
    agent = SupervisorAgent()
    
    # Analyze request
    strategy = agent.analyze_optimization_request(jobs, machines, constraint)
    print("OPTIMIZATION STRATEGY:")
    print(strategy)
    
    # Test schedule selection (mock candidates)
    schedule1 = Schedule()
    schedule1.kpis = KPI(total_tardiness=20, total_setup_time=50, num_setup_switches=3)
    
    schedule2 = Schedule()
    schedule2.kpis = KPI(total_tardiness=10, total_setup_time=60, num_setup_switches=4)
    
    candidates = [
        (schedule1, "Batching-Optimized"),
        (schedule2, "Load-Balanced")
    ]
    
    best, explanation = agent.select_best_schedule(candidates, constraint)
    print("\n" + explanation)
