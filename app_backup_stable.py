import streamlit as st
from PIL import Image
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import os
import io
from datetime import datetime
from fpdf import FPDF

from utils.xray_engine import XRayDiagnosisEngine
from utils.ecg_engine import ECGDiagnosisEngine

# Page configuration
st.set_page_config(
    page_title="AuraMed | Explainable AI CDSS",
    page_icon="🩻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom PACS / Clinical Styling
st.markdown("""
<style>
    .main { background-color: #0b0f19; }
    .metric-card {
        background: #151c2e;
        border: 1px solid #222f4c;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-urgent {
        background-color: #7f1d1d;
        color: #fecaca;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 13px;
    }
    .badge-routine {
        background-color: #064e3b;
        color: #a7f3d0;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_engines():
    return XRayDiagnosisEngine(), ECGDiagnosisEngine()

xray_engine, ecg_engine = load_engines()

# Sidebar: Patient Session Metadata
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/caduceus.png", width=64)
    st.markdown("### Clinical Triage Session")
    patient_id = st.text_input("Patient ID", value="PX-884920")
    radiologist = st.text_input("Reviewing Clinician", value="Dr. J. Smith, MD")
    accession_date = st.date_input("Exam Date", value=datetime.today())
    st.divider()
    st.info("System operational: Dual ResNet-50 & 1D-CNN XAI pipelines loaded.")

st.title("🩻 AuraMed — Explainable AI Clinical Decision Support")
st.caption("Deep Learning Assisted Multi-Region Radiography & Electrocardiography Diagnostic Triage")

tab1, tab2 = st.tabs(["🩻 Radiography Triage (Chest)", "📈 1D Electrocardiography"])

# ----------------- TAB 1: RADIOGRAPHY -----------------
with tab1:
    col_input, col_view = st.columns([1, 2], gap="large")
    
    with col_input:
        st.subheader("1. Modality Input")
        use_sample = st.checkbox("Use Demo Patient Scan", value=True)
        
        uploaded_img = None
        if use_sample:
            sample_path = os.path.join("sample_data", "sample_chest.png")
            if os.path.exists(sample_path):
                uploaded_img = Image.open(sample_path)
                st.caption("Loaded scan: `sample_data/sample_chest.png`")
        else:
            file = st.file_uploader("Upload Radiograph (PNG, JPG, DICOM-export)", type=["png", "jpg", "jpeg"])
            if file:
                uploaded_img = Image.open(file)

        opacity = st.slider("Grad-CAM Activation Blend", 0.1, 0.9, 0.45, 0.05)
        st.caption("Adjust to tune transparency over the raw anatomical field.")

    with col_view:
        st.subheader("2. Dual-Viewport Diagnostic Inspection")
        if uploaded_img:
            diag, conf, heatmap_colored, heatmap_filtered = xray_engine.process_and_explain(uploaded_img)
            
            # Selective alpha blend: only blend pixels where activation exceeds threshold
            orig_np = np.array(uploaded_img.convert("RGB"))
            alpha = np.expand_dims(heatmap_filtered, axis=2) * opacity
            blended = (orig_np * (1.0 - alpha) + heatmap_colored * alpha).astype(np.uint8)

            v1, v2 = st.columns(2)
            with v1:
                st.markdown("**Original Scintigram / Scan**")
                st.image(uploaded_img, width="stretch")
            with v2:
                st.markdown("**Pathological Attention (Grad-CAM)**")
                st.image(blended, width="stretch")

            # Triage Classification Metrics
            is_urgent = "Pneumonia" in diag or "Lesion" in diag
            badge_html = '<span class="badge-urgent">URGENT TRIAGE</span>' if is_urgent else '<span class="badge-routine">ROUTINE EVALUATION</span>'
            
            st.markdown(f"""
            <div class="metric-card">
                <h4>Diagnostic Readout {badge_html}</h4>
                <p style="font-size: 20px; font-weight: 600; margin: 4px 0;">{diag}</p>
                <p style="color: #94a3b8; margin: 0;">Inference Confidence: <b>{conf*100:.1f}%</b></p>
                <p style="font-size: 13px; color: #64748b; margin-top: 6px;">Grad-CAM regions isolate localized pixel gradients with highest attribution toward the predicted pathology.</p>
            </div>
            """, unsafe_allow_html=True)

            # PDF Report Export
            def generate_xray_pdf():
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, "CLINICAL AUDIT & XAI TRIAGE REPORT", ln=True, align="C")
                pdf.set_font("Helvetica", size=10)
                pdf.cell(0, 8, f"Patient ID: {patient_id} | Date: {accession_date} | Clinician: {radiologist}", ln=True, align="C")
                pdf.ln(5)
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, "Primary Findings:", ln=True)
                pdf.set_font("Helvetica", size=11)
                pdf.cell(0, 7, f"- Predicted Classification: {diag}", ln=True)
                pdf.cell(0, 7, f"- Confidence Score: {conf*100:.2f}%", ln=True)
                pdf.cell(0, 7, f"- Triage Priority: {'URGENT' if is_urgent else 'ROUTINE'}", ln=True)
                pdf.ln(5)
                
                # Save temp blended image into PDF
                temp_img_path = "sample_data/temp_audit.png"
                Image.fromarray(blended).save(temp_img_path)
                pdf.image(temp_img_path, x=45, w=120)
                
                pdf.ln(5)
                pdf.set_font("Helvetica", "I", 9)
                pdf.multi_cell(0, 5, "Disclaimer: Automated XAI Decision Support output. Findings require mandatory verification by a board-certified radiologist prior to clinical intervention.")
                return pdf.output()

            pdf_data = generate_xray_pdf()
            st.download_button(
                label="📄 Download Clinical Audit PDF Report",
                data=bytes(pdf_data),
                file_name=f"Audit_Report_{patient_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Select or upload a radiograph to begin triage.")

# ----------------- TAB 2: 1D ECG -----------------
with tab2:
    st.subheader("1. 187-Point ECG Beat Sequence")
    use_sample_ecg = st.checkbox("Use Demo ECG Heartbeat", value=True)
    
    signal = None
    if use_sample_ecg:
        sample_ecg_path = os.path.join("sample_data", "sample_ecg.csv")
        if os.path.exists(sample_ecg_path):
            df = pd.read_csv(sample_ecg_path, header=None)
            signal = df.iloc[0, :187].values.astype(float)
            st.caption("Loaded: `sample_data/sample_ecg.csv`")
    else:
        sample_file = st.file_uploader("Upload CSV single-beat record", type=["csv"])
        if sample_file:
            df = pd.read_csv(sample_file, header=None)
            signal = df.iloc[0, :187].values.astype(float)

    if signal is not None:
        diag, conf, saliency = ecg_engine.process_and_explain(signal)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=signal, mode='lines', name='ECG Voltage', line=dict(color='#38bdf8', width=2.5)))
        
        high_risk_idx = np.where(saliency > 0.6)[0]
        fig.add_trace(go.Scatter(
            x=high_risk_idx, 
            y=signal[high_risk_idx], 
            mode='markers', 
            name='Attribution Peaks', 
            marker=dict(color='#ef4444', size=8, symbol='circle')
        ))
        
        fig.update_layout(
            paper_bgcolor="#151c2e",
            plot_bgcolor="#0b0f19",
            font=dict(color="#e2e8f0"),
            title="Morphology Waveform & Saliency Activation Triggers",
            xaxis=dict(title="Temporal Index (125 Hz)", gridcolor="#1e293b"),
            yaxis=dict(title="Normalized Amplitude", gridcolor="#1e293b")
        )
        st.plotly_chart(fig, width="stretch")
        st.warning(f"**Arrhythmia Classification:** {diag} ({conf * 100:.1f}% confidence)")