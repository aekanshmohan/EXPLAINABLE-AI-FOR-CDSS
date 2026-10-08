# Clinical XAI CDSS Project Rules

- **Framework**: Streamlit, PyTorch, Torchvision, Plotly, FPDF.
- **Authentication**: `streamlit-authenticator` using Bcrypt credentials in `config.yaml`.
- **Compliance & Privacy**:
  - Ephemeral processing only (Zero-Retention: no patient biometrics or scans saved to disk permanently).
  - WCAG 2.1 AA high-contrast slate theme (`#0a0f1d`, `#151d30`, `#38bdf8`).
  - Strict human-in-the-loop clinical disclaimers.
- **Explainability**:
  - Radiography: ResNet-50 with Grad-CAM (`layer4`).
  - ECG: 1D-CNN with backpropagated temporal saliency peaks.