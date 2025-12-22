"""
Core data models package for the Multi-Agent Production Job Optimizer.

This package contains all data structures used throughout the system:
- Job: Represents a production job to be scheduled
- Machine: Represents a production machine with constraints
- Schedule: Represents a complete production schedule
- KPI: Key Performance Indicators for schedule evaluation
"""

__all__ = ['Job', 'Machine', 'Schedule', 'KPI', 'Constraint']
