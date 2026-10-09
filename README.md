# 🏥 XAI CDSS: Explainable AI Clinical Decision Support System

[![Next.js](https://img.shields.io/badge/Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://reactjs.org/)

XAI CDSS is an advanced, end-to-end Clinical Decision Support System designed to assist medical professionals by providing AI-driven diagnostic insights with full visual explainability. By integrating medical imaging and physiological data analysis with transparent AI models, the system ensures clinicians retain full interpretive context and trust in automated assessments.

## 🚀 Key Features

*   **Multi-Modal Diagnostic Engines:** Automated preliminary analysis for Chest X-ray abnormalities, ECG rhythm classification, and anatomical fracture detection.
*   **Model Transparency (XAI):** Generates real-time Grad-CAM and saliency map visualizations, allowing clinicians to see exactly *where* and *why* the AI made a specific prediction.
*   **Complete Clinical Workflow:** Features secure clinician authentication, patient intake routing, and DICOM file de-identification and processing.
*   **Adjudication & Auditing:** Clinicians can review AI confidence scores, append their final professional risk assessments, and maintain history via SQLite storage.
*   **Automated Reporting:** Generates signed, downloadable PDF audit reports summarizing AI findings alongside the clinician's final adjudication.

## 💻 Technology Stack

**Frontend (Clinical Workstation)**
*   **Framework:** Next.js / React
*   **Styling:** Tailwind CSS
*   **Architecture:** Component-based UI with dedicated patient workflow, risk review, and transparency views.

**Backend & AI Services**
*   **API Framework:** FastAPI (Python)
*   **AI/ML Engines:** PyTorch (Custom diagnostic models for X-ray and ECG)
*   **Explainability:** Grad-CAM & Saliency mapping algorithms
*   **Database:** SQLite (Assessment records and audit logging)

## 📂 System Architecture

For a comprehensive breakdown of the data flow, internal module connections, and system design, please view the [Architecture Documentation](ARCHITECTURE.md).

## 🛠️ Getting Started (Local Development)

To run this application locally, you will need two terminal instances to run the separated backend and frontend environments. 

### Prerequisites
*   Node.js (v18+)
*   Python (3.8+)
*   Standard ML libraries (PyTorch, OpenCV, NumPy)

### 1. Start the Backend API
Open your first terminal in the root directory of the project and run the FastAPI server:
```bash
# Install requirements (if running for the first time)
pip install -r requirements.txt

# Start the Python backend service
python api.py