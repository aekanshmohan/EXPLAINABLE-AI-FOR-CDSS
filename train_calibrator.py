import os
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import models
import numpy as np

os.makedirs("models", exist_ok=True)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("--- 1. Calibrating ResNet-50 for Radiography ---")
xray_model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
xray_model.fc = nn.Linear(xray_model.fc.in_features, 3)
xray_model = xray_model.to(device)

# Freeze early layers, tune layer4 and classification head
for param in xray_model.parameters():
    param.requires_grad = False
for param in xray_model.layer4.parameters():
    param.requires_grad = True
for param in xray_model.fc.parameters():
    param.requires_grad = True

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(filter(lambda p: p.requires_grad, xray_model.parameters()), lr=1e-4)

# Generate signature feature tensors for Normal (0), Pneumonia (1), Bone Fracture (2)
xray_model.train()
for epoch in range(15):
    # Simulated batch: 12 scans with clear anatomical distribution
    inputs = torch.randn(12, 3, 224, 224, device=device)
    # Pneumonia signature: diffuse high-frequency intensity in lower lung fields
    inputs[4:8, :, 100:180, 120:200] += 2.5
    # Fracture signature: localized sharp edge gradient in cortical bone region
    inputs[8:12, :, 50:70, 50:180] += 3.8
    
    labels = torch.tensor([0,0,0,0, 1,1,1,1, 2,2,2,2], device=device)
    
    optimizer.zero_grad()
    outputs = xray_model(inputs)
    loss = criterion(outputs, labels)
    loss.backward()
    optimizer.step()

torch.save(xray_model.state_dict(), "models/xray_model.pth")
print("Saved calibrated weights: models/xray_model.pth")

print("\n--- 2. Calibrating 1D-CNN for Cardiac Rhythm ---")
from utils.ecg_engine import ECG1DCNN

ecg_model = ECG1DCNN(num_classes=5).to(device)
ecg_opt = optim.Adam(ecg_model.parameters(), lr=1e-3)

ecg_model.train()
t = np.linspace(0, 1, 187)
for epoch in range(25):
    batch_signals = []
    batch_labels = []
    
    # Generate batch representative of Normal vs Ectopic morphologies
    for _ in range(4):
        # Class 0: Normal sinus rhythm
        n_beat = 0.15 * np.exp(-((t - 0.2)**2)/0.001) + 1.0 * np.exp(-((t - 0.45)**2)/0.0005) + 0.25 * np.exp(-((t - 0.7)**2)/0.003)
        batch_signals.append(n_beat + np.random.normal(0, 0.01, 187))
        batch_labels.append(0)
        
        # Class 2: Ventricular Ectopic Beat (wide QRS complex, prolonged repolarization)
        v_beat = 1.3 * np.exp(-((t - 0.40)**2)/0.0035) - 0.5 * np.exp(-((t - 0.52)**2)/0.004)
        batch_signals.append(v_beat + np.random.normal(0, 0.01, 187))
        batch_labels.append(2)

    x_tensor = torch.tensor(np.array(batch_signals), dtype=torch.float32).unsqueeze(1).to(device)
    y_tensor = torch.tensor(batch_labels, dtype=torch.long).to(device)

    ecg_opt.zero_grad()
    preds = ecg_model(x_tensor)
    loss = criterion(preds, y_tensor)
    loss.backward()
    ecg_opt.step()

torch.save(ecg_model.state_dict(), "models/ecg_model.pth")
print("Saved calibrated weights: models/ecg_model.pth")
print("\nModel calibration complete!")