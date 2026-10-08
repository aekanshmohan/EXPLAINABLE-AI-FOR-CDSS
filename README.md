# Explainable AI for Clinical Decision Support Systems (CDSS)

This repository contains an end-to-end, production-grade clinical workstation designed to provide AI-assisted diagnostics, dynamic patient workflows, and robust clinical auditing. It integrates deep learning models for radiography and ECG analysis with a strict, Explainable AI (XAI) transparency layer.

## 🚀 Core Features
* **Multi-Modal AI Diagnostics:** 
  * **Chest Radiography:** Powered by DenseNet121 for 14-class pulmonary pathology classification.
  * **Orthopedic Fracture Analysis:** Powered by fine-tuned ResNet50 for appendicular and axial cortical disruption.
  * **ECG Rhythm Analysis:** 1D-CNN architecture for waveform classification.
* **Explainable AI (XAI):** Integrated Grad-CAM feature attribution with interactive alpha-blending to visualize local anatomical attributions. Includes a dynamic clinical reasoning engine for all major pathologies.
* **Clinical Workflow State Machine:** Seamless UI routing from Patient Intake and Assessment Selection to Composite Risk Analysis and Clinical Review.
* **Auditable Transparency:** Dedicated model transparency dashboard detailing ROC-AUC metrics, dataset lineage, and known clinical limitations.
* **PDF Export:** One-click generation of hospital-grade, digitally signed patient audit reports.

## 🛠️ Technology Stack
* **Frontend:** Next.js, React, Tailwind CSS, Lucide Icons
* **Backend:** Python, FastAPI, SQLite
* **AI/ML:** PyTorch, Torchvision, OpenCV (Grad-CAM)

## ⚙️ Local Setup & Installation

### 1. Start the FastAPI Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
python api.py