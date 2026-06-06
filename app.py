import streamlit as st
import json
import os
import requests
from dotenv import load_dotenv
from hindsight import retain_incident, recall_incidents, list_memories, delete_all_memories
from llm import extract_structure, generate_triage_brief

load_dotenv()

st.set_page_config(
    page_title="RecallOps | Intelligent Incident Memory Bank",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"], .stText, .stMarkdown, .stButton, .stTextInput, .stTextArea {
        font-family: 'Outfit', sans-serif !important;
    }
    
    .stApp {
        background-color: #0a0b10;
        color: #e2e8f0;
    }
    
    .incident-card {
        background: rgba(22, 24, 38, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
    }
    
    .incident-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 30px rgba(99, 102, 241, 0.15);
        border-color: rgba(99, 102, 241, 0.4);
    }
    
    .incident-title {
        color: #818cf8;
        font-size: 1.35rem;
        font-weight: 700;
        margin-bottom: 12px;
    }
    
    .incident-section {
        margin-top: 10px;
        font-size: 0.95rem;
    }
    
    .section-label {
        font-weight: 600;
        color: #94a3b8;
    }
    
    .section-value {
        color: #f1f5f9;
    }
    
    .badge-container {
        display: flex;
        gap: 8px;
        margin-bottom: 15px;
        flex-wrap: wrap;
    }
    
    .badge {
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border: 1px solid;
    }
    
    .badge-service {
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border-color: rgba(99, 102, 241, 0.3);
    }
    
    .badge-time {
        background: rgba(245, 158, 11, 0.15);
        color: #fde68a;
        border-color: rgba(245, 158, 11, 0.3);
    }
    
    .badge-score {
        background: rgba(16, 185, 129, 0.15);
        color: #a7f3d0;
        border-color: rgba(16, 185, 129, 0.3);
    }
    
    section[data-testid="stSidebar"] {
        background-color: #06070a !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .app-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #a5b4fc 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    
    .app-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 30px;
    }
    
    div[data-baseweb="textarea"] textarea, div[data-baseweb="input"] input {
        background-color: #141622 !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
    }
    
    div[data-baseweb="textarea"] textarea:focus, div[data-baseweb="input"] input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 1px #6366f1 !important;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 28px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3) !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5) !important;
    }
    
    .brief-box {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.25) 0%, rgba(15, 23, 42, 0.25) 100%);
        border-left: 4px solid #6366f1;
        border-radius: 0 16px 16px 0;
        padding: 24px;
        margin-bottom: 25px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
</style>
""", unsafe_allow_html=True)

def credentials_present():
    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    hindsight_ok = bool(os.getenv("HINDSIGHT_API_KEY"))
    hindsight_pipe_ok = bool(os.getenv("HINDSIGHT_PIPELINE_ID"))
    return groq_ok and hindsight_ok and hindsight_pipe_ok

with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/artificial-intelligence.png", width=80)
    st.markdown("<h2 style='margin-top:0;'>RecallOps</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    page = st.radio(
        "Navigate",
        ["📥 Log Incident", "🚨 Triage Alert", "🧠 Memory Bank"],
        index=0
    )
    
    st.markdown("---")
    st.subheader("System Status")
    
    if credentials_present():
        st.success("🤖 API Connections Live")
    else:
        st.warning("⚠️ Credentials Incomplete")
        st.info("Please complete the .env file with your API keys.")

# ─── LOG INCIDENT ───────────────────────────────────────────────────────────
if page == "📥 Log Incident":
    st.markdown("<div class='app-title'>Log a Post-Mortem</div>", unsafe_allow_html=True)
    st.markdown("<div class='app-subtitle'>Ingest Slack logs, error logs, or post-mortem descriptions. Groq will structure the details, and Hindsight will record them.</div>", unsafe_allow_html=True)

    if not credentials_present():
        st.error("Please configure your `.env` file first with valid keys to use this feature.")
    else:
        raw_input = st.text_area(
            "Raw Incident Notes / Slack Transcript",
            height=200,
            placeholder="e.g. prod database went down at 3pm, lots of connection errors. Priya rolled back auth-service and bumped pool size from 10 to 50. Took 9 minutes to stabilize."
        )

        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            submit_btn = st.button("Extract & Remember")
        with col2:
            nuke_btn = st.button("🗑️ Clear & Reload Fresh")
        with col3:
            bulk_load_btn = st.button("📥 Load 20 Mock Incidents")

        if nuke_btn:
            try:
                with st.spinner("🗑️ Clearing old memories..."):
                    delete_all_memories()

                incidents_file = "data/incidents.json"
                with open(incidents_file, "r") as f:
                    mock_incidents = json.load(f)

                my_bar = st.progress(0, text="Re-ingesting fresh data...")
                success_count = 0
                total = len(mock_incidents)
                for idx, inc in enumerate(mock_incidents):
                    if retain_incident(inc):
                        success_count += 1
                    my_bar.progress((idx + 1) / total)

                my_bar.empty()
                st.success(f"✅ Fresh load complete! {success_count}/{total} incidents stored with metadata.")
            except Exception as e:
                st.error(f"Clear & Reload failed: {str(e)}")

        if submit_btn:
            if not raw_input.strip():
                st.warning("Please enter some incident details to process.")
            else:
                try:
                    with st.spinner("🧠 LLM is extracting structure..."):
                        structured = extract_structure(raw_input)

                    st.subheader("Extracted Details")
                    st.json(structured)

                    with st.spinner("💾 Committing to Hindsight memory bank..."):
                        success = retain_incident(structured)

                    if success:
                        st.success("✅ Incident committed to memory successfully!")
                    else:
                        st.error("Failed to commit incident to Hindsight memory.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        if bulk_load_btn:
            try:
                incidents_file = "data/incidents.json"
                if not os.path.exists(incidents_file):
                    st.error(f"Could not find synthetic data file at {incidents_file}")
                else:
                    with open(incidents_file, "r") as f:
                        mock_incidents = json.load(f)

                    my_bar = st.progress(0, text="Ingesting mock data...")
                    success_count = 0
                    total = len(mock_incidents)
                    for idx, inc in enumerate(mock_incidents):
                        with st.spinner(f"Ingesting incident {idx+1}/{total}..."):
                            if retain_incident(inc):
                                success_count += 1
                        my_bar.progress((idx + 1) / total)

                    my_bar.empty()
                    st.success(f"✅ Ingestion complete! Successfully loaded {success_count}/{total} mock incidents into memory.")
            except Exception as e:
                st.error(f"Bulk load failed: {str(e)}")

# ─── TRIAGE ALERT ────────────────────────────────────────────────────────────
elif page == "🚨 Triage Alert":
    st.markdown("<div class='app-title'>Triage Incoming Alert</div>", unsafe_allow_html=True)
    st.markdown("<div class='app-subtitle'>Paste an active production alert. We will query hindsight memory and generate an actionable triage brief.</div>", unsafe_allow_html=True)

    if not credentials_present():
        st.error("Please configure your `.env` file first with valid keys to use this feature.")
    else:
        alert_input = st.text_area(
            "Alert Text",
            height=120,
            placeholder="e.g. ALERT: auth-service CPU usage exceeded 90% for 5 mins, connection pool exhausted"
        )

        if st.button("Analyze & Resolve"):
            if not alert_input.strip():
                st.warning("Please paste an alert to analyze.")
            else:
                try:
                    with st.spinner("🔍 Retrieving semantically similar incidents from Hindsight..."):
                        similar = recall_incidents(alert_input, limit=3)

                    if not similar:
                        st.info("No matching historical incidents found in memory. Generating generic advice.")

                    with st.spinner("🤖 Synthesizing resolution brief..."):
                        brief = generate_triage_brief(alert_input, similar)

                    st.markdown("<div class='brief-box'>", unsafe_allow_html=True)
                    st.subheader("📋 Triage Brief")
                    st.markdown(brief)
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.subheader("📂 Relevant Historical Incidents")
                    if not similar:
                        st.write("Memory is currently empty. Go to **Log Incident** to load records.")
                    else:
                        for inc in similar:
                            struct = inc.get("structured", {})
                            rel_pct = inc.get("relevance_score", 0.0) * 100

                            st.markdown(f"""
                            <div class="incident-card">
                                <div class="incident-title">📍 {struct.get('service_affected', 'Unknown Service').upper()}</div>
                                <div class="badge-container">
                                    <span class="badge badge-service">Service: {struct.get('service_affected', 'N/A')}</span>
                                    <span class="badge badge-time">Resolve Time: {struct.get('time_to_resolve_minutes', 0)} mins</span>
                                    <span class="badge badge-score">Relevance: {rel_pct:.1f}%</span>
                                </div>
                                <div class="incident-section">
                                    <span class="section-label">Symptom Pattern:</span>
                                    <span class="section-value">{struct.get('symptom_pattern', 'N/A')}</span>
                                </div>
                                <div class="incident-section">
                                    <span class="section-label">Root Cause:</span>
                                    <span class="section-value">{struct.get('root_cause', 'N/A')}</span>
                                </div>
                                <div class="incident-section">
                                    <span class="section-label">Fix Applied:</span>
                                    <span class="section-value">{struct.get('fix_applied', 'N/A')}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")

# ─── MEMORY BANK ─────────────────────────────────────────────────────────────
elif page == "🧠 Memory Bank":
    st.markdown("<div class='app-title'>Memory Bank</div>", unsafe_allow_html=True)
    st.markdown("<div class='app-subtitle'>Inspect the collective memory currently stored in your Hindsight Cloud vector engine.</div>", unsafe_allow_html=True)

    if not credentials_present():
        st.error("Please configure your `.env` file first with valid keys to view this page.")
    else:
        try:
            with st.spinner("Fetching memories..."):
                memories = list_memories()

            total_memories = len(memories)

            col1, col2 = st.columns([2, 5])
            with col1:
                st.metric("Total Incidents in Memory", f"{total_memories}")
            with col2:
                services = sorted(list(set(
                    mem.get("structured", {}).get("service_affected", "Unknown") for mem in memories
                )))
                services = ["All Services"] + services
                filter_service = st.selectbox("Filter by Service", services)

            if filter_service != "All Services":
                filtered_memories = [
                    m for m in memories if m.get("structured", {}).get("service_affected") == filter_service
                ]
            else:
                filtered_memories = memories

            st.write("---")

            if not filtered_memories:
                st.info("No memories found. Go to **Log Incident** to load data or run bulk load.")
            else:
                for idx, mem in enumerate(filtered_memories):
                    struct = mem.get("structured", {})
                    st.markdown(f"""
                    <div class="incident-card">
                        <div class="incident-title">💡 Memory #{idx+1}: {struct.get('service_affected', 'Unknown Service').upper()}</div>
                        <div class="badge-container">
                            <span class="badge badge-service">Service: {struct.get('service_affected', 'N/A')}</span>
                            <span class="badge badge-time">Resolve Time: {struct.get('time_to_resolve_minutes', 0)} mins</span>
                        </div>
                        <div class="incident-section">
                            <span class="section-label">Symptom Pattern:</span>
                            <span class="section-value">{struct.get('symptom_pattern', 'N/A')}</span>
                        </div>
                        <div class="incident-section">
                            <span class="section-label">Root Cause:</span>
                            <span class="section-value">{struct.get('root_cause', 'N/A')}</span>
                        </div>
                        <div class="incident-section">
                            <span class="section-label">Fix Applied:</span>
                            <span class="section-value">{struct.get('fix_applied', 'N/A')}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to load memory bank: {str(e)}")
            st.info("Ensure that HINDSIGHT_API_KEY and HINDSIGHT_PIPELINE_ID are correct, and your network connection is active.")
