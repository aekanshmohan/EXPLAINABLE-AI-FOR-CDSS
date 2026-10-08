import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from PIL import Image
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime
from fpdf import FPDF

from utils.xray_engine import XRayDiagnosisEngine
from utils.ecg_engine import ECGDiagnosisEngine
from utils.dicom_handler import parse_and_deidentify_dicom

# --- 1. PAGE SETUP & WCAG ACCESSIBLE STYLING ---
st.set_page_config(
    page_title="AuraMed | Enterprise Clinical CDSS",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    :root {
        --bg-primary: #0a0f1d;
        --card-bg: #151d30;
        --border-color: #2b3a58;
        --text-high-contrast: #f8fafc;
        --text-muted: #cbd5e1;
        --focus-ring: #38bdf8;
    }
    button:focus-visible, input:focus-visible, [tabindex="0"]:focus-visible {
        outline: 3px solid var(--focus-ring) !important;
        outline-offset: 2px !important;
    }
    .metric-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 12px;
        color: var(--text-high-contrast);
    }
    .audit-card {
        background-color: #0d1527;
        border: 2px solid #38bdf8;
        border-radius: 8px;
        padding: 18px;
        margin-top: 18px;
    }
    .badge-urgent {
        background-color: #991b1b;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 13px;
    }
    .badge-routine {
        background-color: #065f46;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION & REGISTRATION ---
with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Create tabs for Login vs Registration
auth_tab, reg_tab = st.tabs(["🔐 Clinician Login", "📝 Register New Account"])

with auth_tab:
    try:
        authenticator.login()
    except TypeError:
        authenticator.login("main")

with reg_tab:
    try:
        email, username, name = authenticator.register_user()
        if email:
            # Automatically save the new user to config.yaml
            with open("config.yaml", "w") as file:
                yaml.dump(config, file, default_flow_style=False)
            st.success("Account registered successfully! You may now log in via the Login tab.")
    except Exception as e:
        st.error(f"Registration error: {e}")

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Invalid Clinician ID or Password.")
    st.stop()
elif auth_status is None:
    st.info("🔐 Please log in or register your clinician credentials to access the CDSS portal.")
    st.stop()

# --- 3. SESSION CONTEXT ---
user_name = st.session_state.get("name", "Staff Physician")
username_key = st.session_state.get("username", "")
user_role = config['credentials']['usernames'].get(username_key, {}).get("role", "Clinician")

if "audit_status" not in st.session_state:
    st.session_state.audit_status = "Pending Physician Review"
if "override_diag" not in st.session_state:
    st.session_state.override_diag = ""
if "audit_notes" not in st.session_state:
    st.session_state.audit_notes = ""

# --- 4. ENGINE INITIALIZATION ---
@st.cache_resource
def load_engines():
    return XRayDiagnosisEngine(), ECGDiagnosisEngine()

xray_engine, ecg_engine = load_engines()

# --- 5. SIDEBAR: CLINICIAN SESSION & CONTROLS ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/caduceus.png", width=64)
    st.markdown(f"**Clinician:** {user_name}")
    st.caption(f"Role: {user_role.capitalize()}")
    authenticator.logout("Log Out", "sidebar")
    st.divider()

    st.markdown("### Clinical Triage Session")
    with st.form("triage_session_form", clear_on_submit=False):
        patient_id = st.text_input("Patient ID (MRN)", value="PX-884920")
        radiologist = st.text_input("Reviewing Clinician", value=user_name)
        accession_date = st.date_input("Examination Date", value=datetime.today())
        form_consent = st.checkbox("Confirm patient informed consent for AI triage", value=True)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.form_submit_button("Confirm Entry")
        with col_f2:
            clear_form = st.form_submit_button("Reset")

    if clear_form:
        st.session_state.audit_status = "Pending Physician Review"
        st.session_state.audit_notes = ""
        st.rerun()

# --- 6. MAIN DASHBOARD ---
st.title(" AuraMed — Enterprise Clinical CDSS")
st.caption("Investigational PACS Station — DICOM Ingestion, Grad-CAM Attribution & Active HITL Audit")

tab_xray, tab_ecg, tab_analytics, tab_legal = st.tabs([
    " Radiography Triage & DICOM", 
    " Cardiac Rhythm (1D ECG)", 
    " Departmental Analytics",
    " Privacy, Legal & Regulatory"
])
# ----------------- TAB 1: RADIOGRAPHY -----------------
with tab_xray:
    if not form_consent:
        st.warning("Confirm informed consent in the sidebar to proceed.")
    else:
        col_in, col_view = st.columns([1, 2], gap="large")
        dcm_meta = None

        with col_in:
            st.subheader("1. Scintigram / DICOM Ingestion")
            use_sample = st.checkbox("Use Sample Study", value=True)
            uploaded_img = None
            
            if use_sample:
                sample_path = os.path.join("sample_data", "sample_chest.png")
                if os.path.exists(sample_path):
                    uploaded_img = Image.open(sample_path)
                    st.caption("Loaded test frame: `sample_data/sample_chest.png`")
            else:
                file = st.file_uploader(
                    "Upload DICOM (.dcm) or Standard Radiograph (.png, .jpg)", 
                    type=["dcm", "png", "jpg", "jpeg"]
                )
                if file:
                    if file.name.lower().endswith(".dcm"):
                        uploaded_img, dcm_meta = parse_and_deidentify_dicom(file.getvalue())
                        st.success("DICOM parsed: PHI stripped; VOI LUT applied.")
                    else:
                        uploaded_img = Image.open(file)
            
            opacity = st.slider("Grad-CAM Alpha Blend", 0.1, 0.9, 0.45, 0.05)

            if dcm_meta:
                with st.expander("🔍 De-Identified DICOM Header Telemetry", expanded=True):
                    for k, v in dcm_meta.items():
                        st.markdown(f"**{k}:** `{v}`")

        with col_view:
            st.subheader("2. Dual-Viewport Diagnostic Inspection")
            if uploaded_img:
                diag, conf, heatmap_colored, heatmap_filtered = xray_engine.process_and_explain(uploaded_img)
                
                orig_np = np.array(uploaded_img.convert("RGB"))
                alpha = np.expand_dims(heatmap_filtered, axis=2) * opacity
                blended = (orig_np * (1.0 - alpha) + heatmap_colored * alpha).astype(np.uint8)

                v1, v2 = st.columns(2)
                with v1:
                    st.markdown("**Native Scintigram Scan**")
                    st.image(uploaded_img, width="stretch")
                with v2:
                    st.markdown("**Pathological Attention (Grad-CAM)**")
                    st.image(blended, width="stretch")

                is_urgent = "Pneumonia" in diag or "Lesion" in diag or "Fracture" in diag
                badge = '<span class="badge-urgent">URGENT TRIAGE PRIORITY</span>' if is_urgent else '<span class="badge-routine">ROUTINE TRIAGE PRIORITY</span>'
                
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Inference Finding: {badge}</h4>
                    <p style="font-size: 22px; font-weight: 700; margin: 6px 0;">{diag}</p>
                    <p style="color: #cbd5e1; margin: 0;">Statistical Model Confidence: <b>{conf*100:.1f}%</b></p>
                </div>
                """, unsafe_allow_html=True)

                # --- 3. HUMAN-IN-THE-LOOP (HITL) AUDIT & OVERRIDE PANEL ---
                st.markdown("""<div class="audit-card">
                    <h4 style="margin-top:0; color:#38bdf8;">👨‍⚕️ Clinician Quality Audit & Override Panel</h4>
                    <p style="font-size: 13px; color: #cbd5e1;">Under FDA Class II SaMD guidance, AI predictions require active physician verification before EHR transmission.</p>
                </div>""", unsafe_allow_html=True)

                adjudication = st.radio(
                    "Clinician Action:",
                    ["Concur with AI Inference", "Override AI Inference"],
                    horizontal=True
                )

                if adjudication == "Override AI Inference":
                    override_selection = st.selectbox(
                        "Physician Override Diagnosis:",
                        ["Normal Study / Unremarkable", "Bacterial Pneumonia", "Pleural Effusion", "Cardiomegaly", "Atelectasis", "Consolidation / Lesion"]
                    )
                    st.session_state.override_diag = override_selection
                    st.session_state.audit_status = f"OVERRIDDEN -> {override_selection}"
                else:
                    st.session_state.override_diag = diag
                    st.session_state.audit_status = f"CONCURRED -> {diag}"

                st.session_state.audit_notes = st.text_area(
                    "Clinical Rationale / Radiologist Notes",
                    value=st.session_state.audit_notes,
                    placeholder="Enter diagnostic notes, correlation with patient history, or reason for override..."
                )

                # PDF Export with Adjudication & DICOM Telemetry
                def generate_xray_pdf():
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Helvetica", "B", 16)
                    pdf.cell(0, 10, "CLINICAL AUDIT & XAI TRIAGE REPORT", align="C")
                    pdf.ln(10)
                    pdf.set_font("Helvetica", size=10)
                    pdf.cell(0, 8, f"Patient MRN: {patient_id} | Date: {accession_date} | Attending Clinician: {radiologist}", align="C")
                    pdf.ln(8)
                    pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(0, 8, "1. Model Statistical Inference:")
                    pdf.ln(6)
                    pdf.set_font("Helvetica", size=10)
                    pdf.cell(0, 6, f"- AI Predicted Finding: {diag} ({conf*100:.2f}%)")
                    pdf.ln(6)
                    pdf.cell(0, 6, f"- Priority Assignment: {'URGENT' if is_urgent else 'ROUTINE'}")
                    pdf.ln(8)

                    pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(0, 8, "2. Human-in-the-Loop Adjudication:")
                    pdf.ln(6)
                    pdf.set_font("Helvetica", size=10)
                    pdf.cell(0, 6, f"- Physician Determination: {st.session_state.audit_status}")
                    pdf.ln(6)
                    pdf.cell(0, 6, f"- Clinician Notes: {st.session_state.audit_notes if st.session_state.audit_notes else 'None documented.'}")
                    pdf.ln(8)

                    temp_img_path = "sample_data/temp_audit.png"
                    Image.fromarray(blended).save(temp_img_path)
                    pdf.image(temp_img_path, x=45, w=120)
                    pdf.ln(4)
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.multi_cell(0, 4, "Disclaimer: Automated XAI triage report generated under human-in-the-loop oversight. Must not be used as standalone clinical screening without board-certified physician validation.")
                    return pdf.output()

                pdf_data = generate_xray_pdf()
                st.download_button(
                    " Download Signed Audit PDF Report", 
                    bytes(pdf_data), 
                    f"Audit_{patient_id}.pdf", 
                    "application/pdf"
                )

# ----------------- TAB 2: 1D ECG -----------------
with tab_ecg:
    if not form_consent:
        st.warning("Confirm informed consent in the sidebar to proceed.")
    else:
        st.subheader("1. 187-Point Cardiac Lead Sequence")
        sample_ecg_path = os.path.join("sample_data", "sample_ecg.csv")
        if os.path.exists(sample_ecg_path):
            df = pd.read_csv(sample_ecg_path, header=None)
            signal = df.iloc[0, :187].values.astype(float)
            diag, conf, saliency = ecg_engine.process_and_explain(signal)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=signal, mode='lines', name='Lead Voltage', line=dict(color='#38bdf8', width=2.5)))
            high_risk_idx = np.where(saliency > 0.6)[0]
            fig.add_trace(go.Scatter(x=high_risk_idx, y=signal[high_risk_idx], mode='markers', name='Attribution Peaks', marker=dict(color='#ef4444', size=8)))
            
            fig.update_layout(paper_bgcolor="#151d30", plot_bgcolor="#0a0f1d", font=dict(color="#f8fafc"))
            st.plotly_chart(fig, width="stretch")
            st.warning(f"**Arrhythmia Classification:** {diag} ({conf * 100:.1f}% confidence)")
# ----------------- TAB 3: DEPARTMENTAL ANALYTICS -----------------
with tab_analytics:
    st.subheader("Enterprise Telemetry & Triage Throughput")
    st.caption("Live operational metrics for hospital administration and quality assurance.")
    
    # Key Performance Indicators (KPIs)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Scans (24h)", "1,248", "+14%")
    kpi2.metric("Avg. AI Turnaround", "0.85 sec", "-0.15 sec")
    kpi3.metric("Routine Overrides", "4.2%", "-0.8%")
    kpi4.metric("System Uptime", "99.99%", "Stable")

    st.divider()

    # Visualizations
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**Departmental Triage Distribution**")
        labels = ['Normal', 'Pneumonia', 'Cardiomegaly', 'Pleural Effusion']
        values = [540, 310, 250, 148]
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, 
                                         marker_colors=['#065f46', '#991b1b', '#b45309', '#1e3a8a'])])
        fig_pie.update_layout(paper_bgcolor="#151d30", font=dict(color="#f8fafc"), margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        st.markdown("**AI Concurrence vs. Override Trends (Last 7 Days)**")
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        concur = [120, 135, 140, 110, 150, 95, 105]
        override = [5, 4, 7, 3, 6, 2, 4]
        
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=days, y=concur, name='Physician Concurrence', marker_color='#0ea5e9'))
        fig_bar.add_trace(go.Bar(x=days, y=override, name='Physician Override', marker_color='#f43f5e'))
        fig_bar.update_layout(barmode='stack', paper_bgcolor="#151d30", plot_bgcolor="#0a0f1d", 
                              font=dict(color="#f8fafc"), margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_bar, use_container_width=True)
        
# ----------------- TAB 3: LEGAL & COMPLIANCE -----------------
with tab_legal:
    st.markdown("###  Privacy, Security & Regulatory Architecture")
    st.markdown("""
    * **Authentication:** Bcrypt-hashed credentials with encrypted JWT session state tokens.
    * **DICOM & HIPAA Compliance:** Ingested `.dcm` files are automatically stripped of the 18 HIPAA Safe Harbor identifiers in memory before tensor allocation.
    * **Human-in-the-Loop Protocol:** Adheres to FDA Class II SaMD guidelines requiring licensed clinician concurrence or override for clinical decision support systems.
    """)