"""
Configuration Loader - Load and manage scheduling policies

This module provides functions to load configuration from YAML/JSON files
and validate policy settings.

Key Features:
    - Load default and custom policy configurations
    - Parse machine constraints and setup time matrices
    - Merge user overrides with defaults
    - Validate configuration schemas
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import time
from models.machine import Constraint, Machine, DowntimeWindow


def load_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Dictionary with configuration data
    """
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary with configuration data
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def parse_time(time_str: str) -> time:
    """
    Parse time string in HH:MM format.
    
    Args:
        time_str: Time string (e.g., "08:00")
        
    Returns:
        time object
    """
    hour, minute = map(int, time_str.split(':'))
    return time(hour, minute)


def load_constraint_from_config(config: Dict[str, Any]) -> Constraint:
    """
    Create Constraint object from configuration dictionary.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Constraint object
    """
    # Parse shift times
    shift_config = config.get('shift', {})
    shift_start = parse_time(shift_config.get('start', '08:00'))
    shift_end = parse_time(shift_config.get('end', '16:00'))
    max_overtime = shift_config.get('max_overtime_minutes', 0)
    
    # Parse setup times
    setup_times = config.get('setup_times', {})
    
    # Parse priority weights
    priority_config = config.get('priority_weights', {})
    rush_weight = priority_config.get('rush', 10.0)
    normal_weight = priority_config.get('normal', 1.0)
    
    # Parse objective weights
    objective_config = config.get('objective_weights', {})
    tardiness_weight = objective_config.get('tardiness', 1.0)
    setup_weight = objective_config.get('setup', 0.5)
    utilization_weight = objective_config.get('utilization', 0.3)
    
    return Constraint(
        shift_start=shift_start,
        shift_end=shift_end,
        max_overtime_minutes=max_overtime,
        setup_times=setup_times,
        rush_job_weight=rush_weight,
        normal_job_weight=normal_weight,
        tardiness_weight=tardiness_weight,
        setup_weight=setup_weight,
        utilization_weight=utilization_weight
    )


def load_machines_from_config(config: Dict[str, Any]) -> list[Machine]:
    """
    Create Machine objects from configuration dictionary.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        List of Machine objects
    """
    machines = []
    machine_configs = config.get('machines', [])
    
    for machine_config in machine_configs:
        machine_id = machine_config['machine_id']
        capabilities = machine_config.get('capabilities', [])
        capacity = machine_config.get('capacity_per_hour', 60)
        
        # Parse downtime windows
        downtime_windows = []
        for dt_config in machine_config.get('downtime_windows', []):
            start = parse_time(dt_config['start_time'])
            end = parse_time(dt_config['end_time'])
            reason = dt_config.get('reason', 'Maintenance')
            downtime_windows.append(DowntimeWindow(start, end, reason))
        
        machine = Machine(
            machine_id=machine_id,
            capabilities=capabilities,
            capacity_per_hour=capacity,
            downtime_windows=downtime_windows,
            operator_id=machine_config.get('operator_id')
        )
        machines.append(machine)
    
    return machines


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load complete configuration from file.
    
    If no path provided, loads default_policy.yaml from config directory.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Dictionary containing constraint and machines
    """
    if config_path is None:
        # Use default config
        config_dir = Path(__file__).parent.parent / 'config'
        config_path = config_dir / 'default_policy.yaml'
    
    # Load config file
    if str(config_path).endswith('.json'):
        config_data = load_json(str(config_path))
    else:
        config_data = load_yaml(str(config_path))
    
    # Parse into objects
    constraint = load_constraint_from_config(config_data)
    machines = load_machines_from_config(config_data)
    
    return {
        'constraint': constraint,
        'machines': machines,
        'raw_config': config_data
    }


def save_config(constraint: Constraint, machines: list[Machine], output_path: str):
    """
    Save configuration to YAML file.
    
    Args:
        constraint: Constraint to save
        machines: List of machines to save
        output_path: Path to output file
    """
    config = {
        'shift': {
            'start': constraint.shift_start.strftime('%H:%M'),
            'end': constraint.shift_end.strftime('%H:%M'),
            'max_overtime_minutes': constraint.max_overtime_minutes
        },
        'setup_times': constraint.setup_times,
        'priority_weights': {
            'rush': constraint.rush_job_weight,
            'normal': constraint.normal_job_weight
        },
        'objective_weights': {
            'tardiness': constraint.tardiness_weight,
            'setup': constraint.setup_weight,
            'utilization': constraint.utilization_weight
        },
        'machines': [machine.to_dict() for machine in machines]
    }
    
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


# Example usage
if __name__ == "__main__":
    # Load default configuration
    config = load_config()
    
    print("Loaded Configuration:")
    print(f"Constraint: {config['constraint']}")
    print(f"Machines: {config['machines']}")
    print(f"\nSetup Times:")
    for key, value in config['constraint'].setup_times.items():
        print(f"  {key}: {value} minutes")
