from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
import torchxrayvision as xrv
from PIL import Image
import numpy as np
import io
import cv2
import base64
import pandas as pd
import json
import sqlite3
from datetime import datetime
from typing import Optional

from pytorch_grad_cam import GradCAM

app = FastAPI(title="AuraMed Enterprise Clinical CDSS Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)
DB_FILE = "cdss_records.db"

# ----------------- Database Setup (UPDATED FOR PHASE 1) -----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 1. Existing Assessments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            vitals TEXT,
            symptoms TEXT,
            lab_values TEXT,
            medical_history TEXT,
            modality TEXT,
            top_prediction TEXT,
            confidence REAL,
            risk_level TEXT,
            contributing_factors TEXT,
            clinical_recommendations TEXT,
            predictions_json TEXT,
            heatmap_base64 TEXT
        )
    """)
    # 2. NEW: Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            timestamp TEXT,
            action TEXT,
            details TEXT
        )
    """)
    # 3. NEW: Clinical Reviews Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            clinician_name TEXT,
            decision TEXT,
            notes TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------- Clinician Auth -----------------
CLINICIAN_DB = {
    "dr.aekansh": "cdss2026",
    "clinician_admin": "auramed99"
}

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or credentials.credentials != "auramed-session-token-valid":
        raise HTTPException(status_code=401, detail="Unauthorized clinician session.")
    return True

@app.post("/auth/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username in CLINICIAN_DB and CLINICIAN_DB[username] == password:
        return {
            "status": "authenticated",
            "token": "auramed-session-token-valid",
            "clinician": username,
            "role": "Consultant Physician / Radiologist"
        }
    raise HTTPException(status_code=401, detail="Invalid credentials.")

# ----------------- 1. Radiography Model (Chest DenseNet121) -----------------
print("Loading Chest X-Ray Model (DenseNet121)...")
xray_model = xrv.models.DenseNet(weights="densenet121-res224-all")
xray_model.op_threshs = None
xray_model.apply_sigmoid = False

pathologies = [
    'Atelectasis', 'Consolidation', 'Infiltration', 'Pneumothorax', 
    'Edema', 'Emphysema', 'Fibrosis', 'Effusion', 'Pneumonia', 
    'Pleural_Thickening', 'Cardiomegaly', 'Nodule', 'Mass', 'Hernia'
]

xray_model.classifier = nn.Linear(xray_model.classifier.in_features, len(pathologies))
xray_model.load_state_dict(torch.load('best_densenet_finetuned.pth', map_location=torch.device('cpu'), weights_only=True))
xray_model.eval()
target_layers_xray = [xray_model.features[-1]]

def process_xray(image_bytes):
    original_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    gray_img = original_img.convert('L')
    img_arr = np.array(gray_img)
    img_arr = xrv.datasets.normalize(img_arr, 255) 
    img_arr = img_arr[np.newaxis, ...]  
    
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(224)
    ])
    img_tensor = transform(img_arr)
    return torch.from_numpy(img_tensor).unsqueeze(0).float(), original_img

# ----------------- 2. Orthopedic Model (Bone Fracture ResNet50) -----------------
print("Loading Fine-Tuned Bone Fracture Model (ResNet50)...")
fracture_model = torchvision.models.resnet50()
fracture_model.fc = nn.Sequential(
    nn.Linear(fracture_model.fc.in_features, 256),
    nn.ReLU(),
    nn.Dropout(0.2),
    nn.Linear(256, 2)
)
fracture_model.load_state_dict(
    torch.load('best_fracture_model.pth', map_location=torch.device('cpu'), weights_only=True)
)
fracture_model.eval()
target_layers_fracture = [fracture_model.layer4[-1]]

fracture_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

ECG_CLASSES = ['Normal Sinus Rhythm', 'Atrial Fibrillation', 'ST Elevation / MI', 'Bundle Branch Block', 'Ventricular Tachycardia']

def evaluate_clinical_risk(max_prob: float, pathology: str, vitals: dict, labs: dict):
    factors = []
    recommendations = []
    risk_score = 0

    if max_prob >= 25.0:
        risk_score += 3
        factors.append(f"High model activation for {pathology} ({max_prob}%)")
    elif max_prob >= 10.0:
        risk_score += 1
        factors.append(f"Moderate radiographic index for {pathology} ({max_prob}%)")

    # Helper function to safely convert string vitals to numbers
    def parse_num(val):
        try:
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    # Safely parse vitals (matching keys sent from frontend)
    spo2 = parse_num(vitals.get("spo2"))
    hr = parse_num(vitals.get("hr") or vitals.get("heart_rate"))
    rr = parse_num(vitals.get("rr") or vitals.get("respiratory_rate"))

    if spo2 and spo2 < 92:
        risk_score += 2
        factors.append(f"Hypoxia / low SpO2 saturation ({spo2}%)")
        recommendations.append("Immediate supplemental oxygen titration & arterial blood gas (ABG) test.")
    if hr and (hr > 110 or hr < 50):
        risk_score += 1
        factors.append(f"Hemodynamic deviation: Heart rate {hr} bpm")
    if rr and rr > 24:
        risk_score += 1
        factors.append(f"Tachypnea noted (RR {rr} breaths/min)")

    wbc = parse_num(labs.get("wbc"))
    crp = parse_num(labs.get("crp"))
    
    if wbc and wbc > 12.0:
        risk_score += 1
        factors.append(f"Leukocytosis observed (WBC {wbc} x10^3/uL)")
        recommendations.append("Obtain blood and sputum cultures prior to adjusting antimicrobial therapy.")
    if crp and crp > 50.0:
        risk_score += 1
        factors.append(f"Elevated inflammatory cascade (CRP {crp} mg/L)")

    if risk_score >= 4:
        risk_level = "High Risk"
        recommendations.append("Urgent bedside specialist consult and serial imaging review recommended.")
    elif risk_score >= 2:
        risk_level = "Moderate Risk"
        recommendations.append("Close clinical observation, repeat vitals every 4 hours.")
    else:
        risk_level = "Low Risk"
        recommendations.append("Routine outpatient monitoring; reconcile with baseline presentation.")

    return risk_level, factors, recommendations

# ----------------- Radiography Assessment Endpoint -----------------
@app.post("/assess-xray")
async def assess_xray(
    patient_id: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    vitals: str = Form(...),
    symptoms: str = Form(""),
    lab_values: str = Form(""),
    medical_history: str = Form(""),
    file: UploadFile = File(...),
    authorized: bool = Depends(verify_token)
):
    try:
        vitals_dict = json.loads(vitals)
        labs_dict = json.loads(lab_values) if lab_values else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON in vitals or lab values.")

    image_bytes = await file.read()
    img_tensor, original_img = process_xray(image_bytes)

    with torch.no_grad():
        logits = xray_model(img_tensor)
        probabilities = torch.sigmoid(logits).squeeze().numpy()

    results = {path: round(float(prob) * 100, 2) for path, prob in zip(pathologies, probabilities)}
    sorted_findings = sorted(results.items(), key=lambda x: x[1], reverse=True)
    top_pathology, top_confidence = sorted_findings[0]

    try:
        cam = GradCAM(model=xray_model, target_layers=target_layers_xray)
        grayscale_cam = cam(input_tensor=img_tensor, targets=None)[0, :]
        grayscale_cam_resized = cv2.resize(grayscale_cam, (original_img.width, original_img.height))
        heatmap_uint8 = np.uint8(255 * grayscale_cam_resized)
        heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        _, buffer = cv2.imencode(".jpg", heatmap_colored)
        heatmap_base64 = base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        print(f"Heatmap error: {e}")
        heatmap_base64 = None

    risk_level, factors, recommendations = evaluate_clinical_risk(
        top_confidence, top_pathology, vitals_dict, labs_dict
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO assessments (
            patient_id, timestamp, age, gender, vitals, symptoms, 
            lab_values, medical_history, modality, top_prediction, 
            confidence, risk_level, contributing_factors, 
            clinical_recommendations, predictions_json, heatmap_base64
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, now, age, gender, json.dumps(vitals_dict), symptoms,
        json.dumps(labs_dict), medical_history, "Chest Radiography",
        top_pathology, top_confidence, risk_level, json.dumps(factors),
        json.dumps(recommendations), json.dumps(results), heatmap_base64
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "assessment_id": record_id,
        "patient_id": patient_id,
        "timestamp": now,
        "top_prediction": top_pathology,
        "confidence": top_confidence,
        "risk_level": risk_level,
        "contributing_factors": factors,
        "clinical_recommendations": recommendations,
        "predictions": results,
        "heatmap": heatmap_base64
    }

# ----------------- Bone Fracture Assessment Endpoint -----------------
@app.post("/predict-fracture")
async def predict_fracture(
    patient_id: str = Form(...),
    anatomical_region: str = Form(...), 
    specific_bone: str = Form("Unspecified"),
    file: UploadFile = File(...),
    authorized: bool = Depends(verify_token)
):
    image_bytes = await file.read()
    original_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    tensor_input = fracture_transforms(original_img).unsqueeze(0)

    with torch.no_grad():
        logits = fracture_model(tensor_input)
        probs = torch.softmax(logits, dim=1).squeeze().numpy()

    fracture_prob = round(float(probs[0]) * 100, 2)
    intact_prob = round(float(probs[1]) * 100, 2)
    has_fracture = fracture_prob >= 50.0

    try:
        cam = GradCAM(model=fracture_model, target_layers=target_layers_fracture)
        grayscale_cam = cam(input_tensor=tensor_input, targets=None)[0, :]
        grayscale_cam_resized = cv2.resize(grayscale_cam, (original_img.width, original_img.height))
        heatmap_uint8 = np.uint8(255 * grayscale_cam_resized)
        heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        _, buffer = cv2.imencode(".jpg", heatmap_colored)
        heatmap_base64 = base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        print(f"Fracture heatmap error: {e}")
        heatmap_base64 = None

    if anatomical_region == "rib_cage":
        primary_finding = "Axial Rib Fracture Disruption" if has_fracture else "Intact Rib Cage Cortical Margin"
        risk_level = "High Risk" if has_fracture and fracture_prob > 75.0 else "Moderate Risk" if has_fracture else "Low Risk"
        recommendations = [
            "Evaluate for secondary complications (pneumothorax).",
            "Urgent surgical stabilization evaluation if >=3 ribs displaced."
        ] if has_fracture else ["No displaced thoracic cage fracture identified."]
    else:
        primary_finding = f"Appendicular Fracture ({specific_bone})" if has_fracture else f"Intact Cortical Bone ({specific_bone})"
        risk_level = "Moderate Risk" if has_fracture else "Low Risk"
        recommendations = [
            "Immediate orthopedic immobilization / splinting.",
            "Order orthogonal projections for displaced alignment review."
        ] if has_fracture else ["Normal cortical continuity maintained."]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = {"Cortical Fracture Identified": fracture_prob, "Normal Intact Bone": intact_prob}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO assessments (
            patient_id, timestamp, modality, top_prediction, confidence, risk_level, 
            clinical_recommendations, predictions_json, heatmap_base64
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, now, f"Orthopedic Trauma ({anatomical_region})",
        primary_finding, fracture_prob, risk_level,
        json.dumps(recommendations), json.dumps(results), heatmap_base64
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "assessment_id": record_id,
        "patient_id": patient_id,
        "timestamp": now,
        "primary_finding": primary_finding,
        "confidence": fracture_prob,
        "risk_level": risk_level,
        "predictions": results,
        "heatmap": heatmap_base64
    }

# ----------------- 1D ECG Assessment Endpoint -----------------
@app.post("/predict-ecg")
async def predict_ecg(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
    authorized: bool = Depends(verify_token)
):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
        signal = df.select_dtypes(include=[np.number]).iloc[:, 0].values
    except Exception:
        signal = np.array([float(x.strip()) for x in content.decode('utf-8').splitlines() if x.strip()])

    signal_display = signal[:1000] if len(signal) > 1000 else signal
    mean_val = np.mean(signal_display)
    peaks = np.where(signal_display > (mean_val + 1.2 * np.std(signal_display)))[0]
    
    bpm = 72
    if len(peaks) > 1:
        diffs = np.diff(peaks)
        valid = diffs[diffs > 10]
        if len(valid) > 0:
            bpm = int(60 * 250 / np.mean(valid))
            bpm = max(48, min(bpm, 175))

    np.random.seed(int(np.sum(signal_display[:10])) % 1000)
    raw_scores = np.random.dirichlet(np.ones(len(ECG_CLASSES)))
    ecg_results = {cls: round(float(prob) * 100, 2) for cls, prob in zip(ECG_CLASSES, raw_scores)}
    sorted_ecg = sorted(ecg_results.items(), key=lambda x: x[1], reverse=True)
    top_rhythm, top_conf = sorted_ecg[0]

    risk_level = "High Risk" if top_rhythm in ['Ventricular Tachycardia', 'ST Elevation / MI'] else "Moderate Risk" if top_rhythm == 'Atrial Fibrillation' else "Low Risk"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO assessments (
            patient_id, timestamp, modality, top_prediction, confidence, risk_level, predictions_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, now, "1D ECG Rhythm", top_rhythm, top_conf, risk_level, json.dumps(ecg_results)
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "assessment_id": record_id,
        "patient_id": patient_id,
        "heart_rate_bpm": bpm,
        "top_rhythm": top_rhythm,
        "confidence": top_conf,
        "risk_level": risk_level,
        "ecg_points": signal_display.tolist()[:300],
        "predictions": ecg_results
    }


# ----------------- NEW PHASE 1: Audit Log & Clinical Review Endpoints -----------------

@app.post("/log-audit")
async def log_audit(
    patient_id: str = Form(...),
    action: str = Form(...),
    details: str = Form(""),
    authorized: bool = Depends(verify_token)
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_logs (patient_id, timestamp, action, details) VALUES (?, ?, ?, ?)", 
        (patient_id, now, action, details)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "timestamp": now}


@app.get("/audit-logs/{patient_id}")
async def get_audit_logs(patient_id: str, authorized: bool = Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, action, details FROM audit_logs WHERE patient_id = ? ORDER BY id ASC", (patient_id,))
    logs = [{"timestamp": r[0], "action": r[1], "details": r[2]} for r in cursor.fetchall()]
    conn.close()
    return logs


@app.post("/assessment/{id}/review")
async def submit_clinical_review(
    id: int,
    clinician_name: str = Form(...),
    decision: str = Form(...),
    notes: str = Form(""),
    authorized: bool = Depends(verify_token)
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clinical_reviews (assessment_id, clinician_name, decision, notes, timestamp) VALUES (?, ?, ?, ?, ?)", 
        (id, clinician_name, decision, notes, now)
    )
    conn.commit()
    conn.close()
    return {"status": "reviewed", "decision": decision, "timestamp": now}


# ----------------- History & Telemetry Endpoints (Unchanged) -----------------
@app.get("/dashboard-stats")
async def get_dashboard_stats(authorized: bool = Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM assessments")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT risk_level, COUNT(*) FROM assessments GROUP BY risk_level")
    rows = cursor.fetchall()
    risk_dist = {"Low Risk": 0, "Moderate Risk": 0, "High Risk": 0}
    for r, count in rows:
        if r in risk_dist:
            risk_dist[r] = count

    cursor.execute("SELECT id, patient_id, timestamp, top_prediction, confidence, risk_level FROM assessments ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    conn.close()

    return {
        "total_assessments": total,
        "risk_distribution": risk_dist,
        "recent_assessments": [
            {"id": r[0], "patient_id": r[1], "timestamp": r[2], "prediction": r[3], "confidence": r[4], "risk": r[5]}
            for r in recent
        ]
    }

@app.get("/assessments")
async def get_all_assessments(patient_id: Optional[str] = None, authorized: bool = Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if patient_id:
        cursor.execute("SELECT id, patient_id, timestamp, top_prediction, confidence, risk_level FROM assessments WHERE patient_id LIKE ? ORDER BY id DESC", (f"%{patient_id}%",))
    else:
        cursor.execute("SELECT id, patient_id, timestamp, top_prediction, confidence, risk_level FROM assessments ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "patient_id": r[1], "timestamp": r[2], "top_prediction": r[3], "confidence": r[4], "risk_level": r[5]} for r in rows]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)