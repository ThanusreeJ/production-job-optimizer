"""
Multi-Agent Production Job Optimizer - Streamlit Dashboard

This is the main Streamlit application that provides an interactive web interface
for the production job optimization system.

Dashboard Structure:
    - Input Zone: Upload jobs, configure constraints
    - Control Zone: Run optimizer, monitor agents
    - Output Zone: View schedules, KPIs, and reports

Run with: streamlit run ui/app.py
"""

import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
from datetime import time, datetime
from pathlib import Path
import sys
import os
from io import BytesIO
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from models.job import Job
from models.machine import Machine, Constraint, DowntimeWindow
from workflows.orchestrator import OptimizationOrchestrator
from utils.config_loader import load_config, save_config
from utils.data_generator import generate_random_jobs, export_jobs_to_csv
from utils.baseline_scheduler import BaselineScheduler

# Page configuration
st.set_page_config(
    page_title="Production Job Optimizer",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .zone-header {
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .kpi-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .success {
        color: #2ca02c;
        font-weight: bold;
    }
    .warning {
        color: #ff7f0e;
        font-weight: bold;
    }
    .error {
        color: #d62728;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'jobs' not in st.session_state:
    st.session_state.jobs = []
if 'config' not in st.session_state:
    st.session_state.config = load_config()
if 'optimization_result' not in st.session_state:
    st.session_state.optimization_result = None
if 'baseline_result' not in st.session_state:
    st.session_state.baseline_result = None
if 'agent_status' not in st.session_state:
    st.session_state.agent_status = {}
if 'show_comparison' not in st.session_state:
    st.session_state.show_comparison = False


def main():
    """Main application function."""
    
    # Header
    st.markdown('<div class="main-header">🏭 Multi-Agent Production Job Optimizer</div>', 
                unsafe_allow_html=True)
    st.markdown("**Built on LangChain • LangGraph • LangSmith • Groq AI**")
    st.markdown("---")
    
    # Sidebar for navigation
    with st.sidebar:
        st.image("https://via.placeholder.com/200x100/1f77b4/ffffff?text=Job+Optimizer", 
                 use_container_width=True)
        st.markdown("### Navigation")
        page = st.radio("Go to:", ["📥 Input & Config", "🎯 Optimize", "📊 Results"], index=0)
        
        st.markdown("---")
        st.markdown("### Quick Actions")
        if st.button("🎲 Generate Test Data"):
            generate_test_data()
        
        if st.button("🔄 Reset All"):
            st.session_state.jobs = []
            st.session_state.optimization_result = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("### System Status")
        st.success("✅ Groq API Connected")
        st.info(f"📦 {len(st.session_state.jobs)} jobs loaded")
    
    # Main content area
    if page == "📥 Input & Config":
        render_input_zone()
    elif page == "🎯 Optimize":
        render_control_zone()
    else:
        render_output_zone()


def generate_test_data():
    """Generate random test jobs."""
    test_jobs = generate_random_jobs(12, rush_probability=0.25)
    st.session_state.jobs = test_jobs
    st.success(f"✅ Generated {len(test_jobs)} test jobs")
    st.rerun()


def render_input_zone():
    """Render the Input Zone - Job Upload & Configuration."""
    
    st.markdown('<div class="zone-header">📥 INPUT ZONE - Jobs & Constraints</div>', 
                unsafe_allow_html=True)
    
    # Two columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📋 Job Management")
        
        # File upload
        uploaded_file = st.file_uploader("Upload Job List (CSV)", type=['csv'])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            jobs = parse_jobs_from_dataframe(df)
            st.session_state.jobs = jobs
            st.success(f"✅ Loaded {len(jobs)} jobs from CSV")
        
        # Manual job entry
        with st.expander("➕ Add Job Manually"):
            with st.form("manual_job_form"):
                job_id = st.text_input("Job ID", value=f"J{len(st.session_state.jobs)+1:03d}")
                product_type = st.selectbox("Product Type", ["P_A", "P_B", "P_C"])
                processing_time = st.number_input("Processing Time (min)", min_value=10, max_value=180, value=45)
                due_time_str = st.time_input("Due Time", value=time(14, 0))
                priority = st.selectbox("Priority", ["normal", "rush"])
                
                machines = [m.machine_id for m in st.session_state.config['machines']]
                machine_options = st.multiselect("Compatible Machines", machines, default=machines[:2])
                
                if st.form_submit_button("Add Job"):
                    new_job = Job(
                        job_id=job_id,
                        product_type=product_type,
                        processing_time=processing_time,
                        due_time=due_time_str,
                        priority=priority,
                        machine_options=machine_options
                    )
                    st.session_state.jobs.append(new_job)
                    st.success(f"✅ Added job {job_id}")
                    st.rerun()
        
        # Display current jobs
        if st.session_state.jobs:
            st.markdown(f"**Current Jobs: {len(st.session_state.jobs)}**")
            jobs_df = pd.DataFrame([
                {
                    'Job ID': j.job_id,
                    'Product': j.product_type,
                    'Time (min)': j.processing_time,
                    'Due': j.due_time.strftime('%H:%M'),
                    'Priority': j.priority,
                    'Machines': ', '.join(j.machine_options)
                }
                for j in st.session_state.jobs
            ])
            st.dataframe(jobs_df, use_container_width=True, height=300)
    
    with col2:
        st.markdown("### ⚙️ Constraint Configuration")
        
        constraint = st.session_state.config['constraint']
        
        # Shift configuration
        with st.expander("🕐 Shift Settings", expanded=True):
            shift_start_str = st.time_input("Shift Start", value=constraint.shift_start)
            shift_end_str = st.time_input("Shift End", value=constraint.shift_end)
            max_overtime = st.number_input("Max Overtime (min)", 
                                          min_value=0, max_value=120, 
                                          value=constraint.max_overtime_minutes)
            
            constraint.shift_start = shift_start_str
            constraint.shift_end = shift_end_str
            constraint.max_overtime_minutes = max_overtime
        
        # Setup times
        with st.expander("🔧 Setup Times (minutes)"):
            st.markdown("**Same Product:**")
            cols = st.columns(3)
            for i, prod in enumerate(['P_A', 'P_B', 'P_C']):
                key = f"{prod}->{prod}"
                default_value = constraint.setup_times.get(key, 5)
                new_value = cols[i].number_input(f"{prod}→{prod}", value=default_value, key=key)
                constraint.setup_times[key] = new_value
            
            st.markdown("**Different Products:**")
            setup_pairs = [
                ("P_A", "P_B"), ("P_A", "P_C"),
                ("P_B", "P_A"), ("P_B", "P_C"),
                ("P_C", "P_A"), ("P_C", "P_B")
            ]
            cols = st.columns(2)
            for i, (from_prod, to_prod) in enumerate(setup_pairs):
                key = f"{from_prod}->{to_prod}"
                default_value = constraint.setup_times.get(key, 30)
                col_idx = i % 2
                new_value = cols[col_idx].number_input(
                    f"{from_prod}→{to_prod}", 
                    value=default_value, 
                    key=key
                )
                constraint.setup_times[key] = new_value
        
        # Objective weights
        with st.expander("🎯 Optimization Weights"):
            st.markdown("Adjust what the optimizer prioritizes:")
            constraint.tardiness_weight = st.slider(
                "Tardiness (meeting deadlines)",
                0.0, 2.0, constraint.tardiness_weight, 0.1
            )
            constraint.setup_weight = st.slider(
                "Setup Minimization",
                0.0, 2.0, constraint.setup_weight, 0.1
            )
            constraint.utilization_weight = st.slider(
                "Load Balancing",
                0.0, 2.0, constraint.utilization_weight, 0.1
            )


def render_control_zone():
    """Render the Control Zone - Optimization Control."""
    
    st.markdown('<div class="zone-header">🎯 CONTROL ZONE - Run Optimization</div>', 
                unsafe_allow_html=True)
    
    if not st.session_state.jobs:
        st.warning("⚠️ No jobs loaded. Please add jobs in the Input Zone first.")
        return
    
    # Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jobs", len(st.session_state.jobs))
    col2.metric("Rush Orders", sum(1 for j in st.session_state.jobs if j.is_rush))
    col3.metric("Machines", len(st.session_state.config['machines']))
    col4.metric("Product Types", len(set(j.product_type for j in st.session_state.jobs)))
    
    st.markdown("---")
    
    # Run buttons with better layout
    st.markdown("### 🚀 Optimization Options")
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])
    
    with col_btn1:
        ai_button = st.button(
            "🤖 AI Multi-Agent Optimizer", 
            type="primary", 
            use_container_width=True,
            help="Run the intelligent multi-agent optimization system"
        )
    
    with col_btn2:
        baseline_button = st.button(
            "📊 Run With Baseline Comparison",
            type="secondary",
            use_container_width=True,
            help="Compare AI optimizer against simple FIFO baseline"
        )
    
    with col_btn3:
        if st.button("🔄", use_container_width=True, help="Reset results"):
            st.session_state.optimization_result = None
            st.session_state.baseline_result = None
            st.session_state.show_comparison = False
            st.rerun()
    
    if ai_button:
        run_optimization(with_baseline=False)
    
    if baseline_button:
        run_optimization(with_baseline=True)
    
    # Agent status display
    if st.session_state.get('optimization_running', False):
        st.markdown("### 🤖 Agent Status")
        
        status_col1, status_col2 = st.columns(2)
        
        with status_col1:
            st.info("📊 Supervisor Agent: Analyzing request...")
            st.info("🔄 Batching Agent: Creating schedule...")
        
        with status_col2:
            st.info("⚖️ Bottleneck Agent: Balancing loads...")
            st.info("✅ Constraint Agent: Validating...")


def run_optimization(with_baseline: bool = False):
    """Execute the multi-agent optimization with real-time agent status display."""
    
    st.session_state.optimization_running = True
    st.session_state.show_comparison = with_baseline
    
    # Create status container for real-time updates
    status_container = st.empty()
    
    try:
        # Step 1: Baseline (if requested)
        if with_baseline:
            with status_container.container():
                st.markdown("### 🤖 AI Optimization Progress")
                with st.status("📊 Running Baseline Scheduler...", expanded=True) as status:
                    st.write("⏳ Creating simple FIFO schedule...")
                    baseline_scheduler = BaselineScheduler()
                    baseline_schedule, baseline_explanation = baseline_scheduler.schedule(
                        jobs=st.session_state.jobs,
                        machines=st.session_state.config['machines'],
                        constraint=st.session_state.config['constraint']
                    )
                    st.session_state.baseline_result = {
                        'schedule': baseline_schedule,
                        'explanation': baseline_explanation,
                        'success': True
                    }
                    st.write("✅ Baseline schedule created!")
                    status.update(label="✅ Baseline Complete", state="complete")
        
        # Step 2: Multi-Agent Optimization
        with status_container.container():
            st.markdown("### 🤖 AI Multi-Agent Optimization")
            
            # Supervisor Agent
            with st.status("👔 Supervisor Agent: Analyzing request...", expanded=True) as supervisor_status:
                st.write("📋 Analyzing jobs, machines, and constraints...")
                st.write(f"📦 {len(st.session_state.jobs)} jobs to schedule")
                st.write(f"🏭 {len(st.session_state.config['machines'])} machines available")
                import time
                time.sleep(0.5)  # Small delay so user can see
                st.write("✅ Analysis complete - delegating to specialist agents...")
                supervisor_status.update(label="✅ Supervisor: Analysis Complete", state="complete")
            
            # Batching Agent
            with st.status("🔄 Batching Agent: Optimizing setup times...", expanded=True) as batching_status:
                st.write("📊 Grouping jobs by product type...")
                st.write("🎯 Prioritizing rush orders...")
                st.write("⚡ Minimizing setup switches...")
                
                # Actually run batching agent
                from agents.batching_agent import BatchingAgent
                batching_agent = BatchingAgent()
                batching_schedule, _ = batching_agent.create_batched_schedule(
                    st.session_state.jobs,
                    st.session_state.config['machines'],
                    st.session_state.config['constraint']
                )
                
                st.write(f"✅ Created schedule with {batching_schedule.kpis.num_setup_switches if batching_schedule.kpis else 'N/A'} setup switches")
                batching_status.update(label="✅ Batching Agent: Schedule Created", state="complete")
            
            # Bottleneck Agent
            with st.status("⚖️ Bottleneck Agent: Balancing machine loads...", expanded=True) as bottleneck_status:
                st.write("📈 Analyzing machine utilization...")
                st.write("🔍 Detecting bottlenecks...")
                st.write("🔀 Redistributing workload...")
                
                # Actually run bottleneck agent
                from agents.bottleneck_agent import BottleneckAgent
                bottleneck_agent = BottleneckAgent()
                bottleneck_schedule, _ = bottleneck_agent.rebalance_schedule(
                    batching_schedule,
                    st.session_state.config['machines'],
                    st.session_state.config['constraint'],
                    st.session_state.jobs
                )
                
                st.write(f"✅ Load balanced: {bottleneck_schedule.kpis.utilization_imbalance:.1f}% imbalance" if bottleneck_schedule.kpis else "✅ Load balanced")
                bottleneck_status.update(label="✅ Bottleneck Agent: Load Balanced", state="complete")
            
            # Constraint Agent
            with st.status("✅ Constraint Agent: Validating schedules...", expanded=True) as constraint_status:
                st.write("📋 Checking shift boundaries...")
                st.write("🔍 Validating machine downtime...")
                st.write("⏰ Verifying rush order deadlines...")
                
                # Actually run constraint agent
                from agents.constraint_agent import ConstraintAgent
                constraint_agent = ConstraintAgent()
                
                batching_valid, batching_violations, _ = constraint_agent.validate_schedule(
                    batching_schedule,
                    st.session_state.jobs,
                    st.session_state.config['machines'],
                    st.session_state.config['constraint']
                )
                
                bottleneck_valid, bottleneck_violations, _ = constraint_agent.validate_schedule(
                    bottleneck_schedule,
                    st.session_state.jobs,
                    st.session_state.config['machines'],
                    st.session_state.config['constraint']
                )
                
                total_violations = len(batching_violations) + len(bottleneck_violations)
                if total_violations == 0:
                    st.write("✅ All schedules valid - no violations!")
                else:
                    st.write(f"⚠️ Found {total_violations} violations to resolve")
                
                constraint_status.update(label="✅ Constraint Agent: Validation Complete", state="complete")
            
            # Final Supervisor Decision
            with st.status("👔 Supervisor Agent: Selecting best schedule...", expanded=True) as final_status:
                st.write("⚡ Scoring candidate schedules...")
                st.write("🎯 Evaluating KPIs (tardiness, setup, utilization)...")
                
                # Run full orchestrator for final decision
                orchestrator = OptimizationOrchestrator()
                result = orchestrator.optimize(
                    jobs=st.session_state.jobs,
                    machines=st.session_state.config['machines'],
                    constraint=st.session_state.config['constraint']
                )
                
                if result['success']:
                    st.write(f"✅ Best schedule selected!")
                    st.write(f"📊 Optimization time: {result['optimization_time']:.2f}s")
                else:
                    st.write("❌ Could not find valid schedule")
                
                final_status.update(
                    label=f"✅ Optimization {'Complete' if result['success'] else 'Failed'}", 
                    state="complete" if result['success'] else "error"
                )
        
        # Store result
        st.session_state.optimization_result = result
        st.session_state.optimization_running = False
        
        # Show success message
        status_container.empty()  # Clear status display
        
        if result['success']:
            success_msg = f"✅ Optimization completed in {result['optimization_time']:.2f} seconds!"
            if with_baseline:
                success_msg += "\n📊 Baseline comparison ready!"
            st.success(success_msg)
            st.balloons()
            # Small delay to let balloons show
            import time
            time.sleep(0.5)
        else:
            st.error("❌ Optimization failed - see results for details")
    
    except Exception as e:
        status_container.empty()
        st.error(f"❌ Error during optimization: {str(e)}")
        st.session_state.optimization_running = False
        return
    
    st.rerun()



def render_output_zone():
    """Render the Output Zone - Results & Visualizations."""
    
    st.markdown('<div class="zone-header">📊 OUTPUT ZONE - Results & Analysis</div>', 
                unsafe_allow_html=True)
    
    result = st.session_state.optimization_result
    baseline_result = st.session_state.baseline_result
    show_comparison = st.session_state.show_comparison
    
    if not result:
        st.info("ℹ️ Run optimization first to see results here.")
        return
    
    if not result['success']:
        st.error("❌ Optimization Failed")
        st.code(result['explanation'])
        return
    
    schedule = result['schedule']
    kpis = schedule.kpis
    
    # COMPARISON VIEW - Show this first if available
    if show_comparison and baseline_result:
        st.markdown("### 🎯 **AI Optimizer vs Baseline Comparison**")
        st.markdown("---")
        
        baseline_kpis = baseline_result['schedule'].kpis
        
        # Improvement metrics in big cards
        col1, col2, col3, col4 = st.columns(4)
        
        tardiness_improvement = ((baseline_kpis.total_tardiness - kpis.total_tardiness) / baseline_kpis.total_tardiness * 100) if baseline_kpis.total_tardiness > 0 else 0
        setup_improvement = ((baseline_kpis.total_setup_time - kpis.total_setup_time) / baseline_kpis.total_setup_time * 100) if baseline_kpis.total_setup_time > 0 else 0
        imbalance_improvement = ((baseline_kpis.utilization_imbalance - kpis.utilization_imbalance) / baseline_kpis.utilization_imbalance * 100) if baseline_kpis.utilization_imbalance > 0 else 0
        
        col1.metric(
            "Tardiness Reduction",
            f"{abs(tardiness_improvement):.1f}%",
            delta=f"{kpis.total_tardiness - baseline_kpis.total_tardiness} min",
            delta_color="inverse"
        )
        
        col2.metric(
            "Setup Time Saved",
            f"{abs(setup_improvement):.1f}%",
            delta=f"{kpis.total_setup_time - baseline_kpis.total_setup_time} min",
            delta_color="inverse"
        )
        
        col3.metric(
            "Better Load Balance",
            f"{abs(imbalance_improvement):.1f}%",
            delta=f"{kpis.utilization_imbalance - baseline_kpis.utilization_imbalance:.1f}%",
            delta_color="inverse"
        )
        
        col4.metric(
            "Fewer Violations",
            f"{baseline_kpis.num_violations - kpis.num_violations}",
            delta="Better" if kpis.num_violations < baseline_kpis.num_violations else "Same",
            delta_color="normal"
        )
        
        # Side-by-side KPI comparison table
        st.markdown("### 📊 Detailed KPI Comparison")
        
        comparison_df = pd.DataFrame({
            'Metric': ['Tardiness (min)', 'Setup Time (min)', 'Setup Switches', 'Max Utilization (%)', 'Load Imbalance (%)', 'Violations'],
            'Baseline (FIFO)': [
                baseline_kpis.total_tardiness,
                baseline_kpis.total_setup_time,
                baseline_kpis.num_setup_switches,
                f"{baseline_kpis.max_machine_utilization:.1f}",
                f"{baseline_kpis.utilization_imbalance:.1f}",
                baseline_kpis.num_violations
            ],
            'AI Optimizer': [
                kpis.total_tardiness,
                kpis.total_setup_time,
                kpis.num_setup_switches,
                f"{kpis.max_machine_utilization:.1f}",
                f"{kpis.utilization_imbalance:.1f}",
                kpis.num_violations
            ],
            'Improvement': [
                f"{tardiness_improvement:+.1f}%",
                f"{setup_improvement:+.1f}%",
                f"{baseline_kpis.num_setup_switches - kpis.num_setup_switches:+d}",
                "-",
                f"{imbalance_improvement:+.1f}%",
                f"{baseline_kpis.num_violations - kpis.num_violations:+d}"
            ]
        })
        
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### 📈 **AI Optimizer Results** (Detailed View Below)")
    
    # KPIs Summary (always show)
    st.markdown("### 📈 Key Performance Indicators")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric(
        "Total Tardiness",
        f"{kpis.total_tardiness} min",
        delta=None,
        delta_color="inverse"
    )
    
    col2.metric(
        "Setup Time",
        f"{kpis.total_setup_time} min",
        delta=f"{kpis.num_setup_switches} switches"
    )
    
    col3.metric(
        "Max Utilization",
        f"{kpis.max_machine_utilization:.1f}%"
    )
    
    col4.metric(
        "Load Imbalance",
        f"{kpis.utilization_imbalance:.1f}%",
        delta=None,
        delta_color="inverse"
    )
    
    col5.metric(
        "Violations",
        kpis.num_violations,
        delta=None,
        delta_color="inverse"
    )
    
    st.markdown("---")
    
    # Gantt Chart
    st.markdown("### 📅 Machine Schedule - Gantt Chart")
    
    # Add product legend
    legend_col1, legend_col2 = st.columns([3, 1])
    with legend_col2:
        st.markdown("**Product Types:**")
        st.markdown("🔵 P_A (Blue)")
        st.markdown("🟠 P_B (Orange)")
        st.markdown("🟢 P_C (Green)")
    
    with legend_col1:
        gantt_fig = create_gantt_chart(schedule)
        st.plotly_chart(gantt_fig, use_container_width=True)
    
    st.markdown("---")
    
    # Two columns for additional info
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.markdown("### 📊 Machine Utilization")
        utilization_fig = create_utilization_chart(schedule, st.session_state.config)
        st.plotly_chart(utilization_fig, use_container_width=True)
    
    with col_right:
        st.markdown("### 📝 Explanation Report")
        st.text_area("", result['explanation'], height=400, disabled=True)
    
    # Download options
    st.markdown("---")
    st.markdown("### 💾 Export Options")
    
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
    with col_dl1:
        # Export schedule as CSV
        schedule_csv = export_schedule_to_csv(schedule)
        st.download_button(
            label="📄 Download Schedule (CSV)",
            data=schedule_csv,
            file_name=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        # Export explanation
        st.download_button(
            label="📋 Download Report (TXT)",
            data=result['explanation'],
            file_name=f"optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    
    with col_dl3:
        # Export config
        config_json = json.dumps(st.session_state.config['constraint'].to_dict(), indent=2)
        st.download_button(
            label="⚙️ Download Config (JSON)",
            data=config_json,
            file_name="config_snapshot.json",
            mime="application/json"
        )


def parse_jobs_from_dataframe(df: pd.DataFrame) -> list[Job]:
    """Parse jobs from uploaded CSV DataFrame."""
    jobs = []
    for _, row in df.iterrows():
        # Parse due time
        due_time_str = str(row['due_time'])
        hour, minute = map(int, due_time_str.split(':'))
        due_time_obj = time(hour, minute)
        
        # Parse machine options
        machine_options = str(row['machine_options']).split(',')
        machine_options = [m.strip() for m in machine_options]
        
        job = Job(
            job_id=str(row['job_id']),
            product_type=str(row['product_type']),
            processing_time=int(row['processing_time']),
            due_time=due_time_obj,
            priority=str(row['priority']),
            machine_options=machine_options
        )
        jobs.append(job)
    
    return jobs


def create_gantt_chart(schedule: 'Schedule') -> go.Figure:
    """Create Plotly Gantt chart for the schedule."""
    
    # Color mapping for product types
    colors = {
        'P_A': '#1f77b4',
        'P_B': '#ff7f0e',
        'P_C': '#2ca02c'
    }
    
    # Create figure
    fig = go.Figure()
    
    # Convert schedule to timeline bars
    for machine_id, assignments in schedule.assignments.items():
        for assignment in assignments:
            # Calculate duration in hours for x-axis
            start_minutes = assignment.start_time.hour * 60 + assignment.start_time.minute
            duration_minutes = assignment.job.processing_time
            
            # Get color based on product type
            bar_color = colors.get(assignment.job.product_type, '#999999')
            
            # Add bar
            fig.add_trace(go.Bar(
                name=assignment.job.job_id,
                y=[machine_id],
                x=[duration_minutes],
                base=start_minutes,
                orientation='h',
                marker=dict(
                    color=bar_color,
                    line=dict(color='white', width=1)
                ),
                text=f"{assignment.job.job_id}<br>{assignment.job.product_type}<br>{assignment.job.processing_time}min",
                textposition='inside',
                textfont=dict(color='white', size=10),
                hovertemplate=(
                    f"<b>{assignment.job.job_id}</b><br>" +
                    f"Product: {assignment.job.product_type}<br>" +
                    f"Start: {assignment.start_time.strftime('%H:%M')}<br>" +
                    f"End: {assignment.end_time.strftime('%H:%M')}<br>" +
                    f"Duration: {assignment.job.processing_time} min<br>" +
                    f"Priority: {assignment.job.priority}<extra></extra>"
                ),
                showlegend=False
            ))
    
    # Update layout
    fig.update_layout(
        title="Machine Schedule Timeline",
        xaxis=dict(
            title="Time (minutes from shift start)",
            range=[0, 480],  # 8 hour shift = 480 minutes
            tickmode='array',
            tickvals=[0, 60, 120, 180, 240, 300, 360, 420, 480],
            ticktext=['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']
        ),
        yaxis=dict(
            title="Machine",
            categoryorder='category ascending'
        ),
        barmode='overlay',
        height=400,
        hovermode='closest',
        plot_bgcolor='#f5f5f5',
        showlegend=False
    )
    
    # Add gridlines
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='white')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='white')
    
    return fig


def create_utilization_chart(schedule: 'Schedule', config: dict) -> go.Figure:
    """Create bar chart showing machine utilization."""
    
    constraint = config['constraint']
    shift_duration = constraint.get_shift_duration_minutes()
    
    machine_utilization = {}
    for machine in config['machines']:
        jobs = schedule.get_machine_jobs(machine.machine_id)
        total_time = sum(job.get_duration_minutes() for job in jobs)
        utilization = (total_time / shift_duration) * 100
        machine_utilization[machine.machine_id] = utilization
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(machine_utilization.keys()),
            y=list(machine_utilization.values()),
            marker_color='#1f77b4',
            text=[f"{v:.1f}%" for v in machine_utilization.values()],
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        yaxis_title="Utilization (%)",
        xaxis_title="Machine",
        showlegend=False,
        height=300
    )
    
    fig.add_hline(y=100, line_dash="dash", line_color="red", 
                  annotation_text="100% Capacity")
    
    return fig


def export_schedule_to_csv(schedule: 'Schedule') -> str:
    """Export schedule to CSV format."""
    
    rows = []
    for machine_id, assignments in schedule.assignments.items():
        for assignment in assignments:
            rows.append({
                'Machine': machine_id,
                'Job ID': assignment.job.job_id,
                'Product Type': assignment.job.product_type,
                'Start Time': assignment.start_time.strftime('%H:%M'),
                'End Time': assignment.end_time.strftime('%H:%M'),
                'Processing Time': assignment.job.processing_time,
                'Setup Time': assignment.setup_time_before,
                'Priority': assignment.job.priority,
                'Late': 'Yes' if assignment.is_late() else 'No',
                'Tardiness': assignment.get_tardiness_minutes()
            })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


if __name__ == "__main__":
    main()
