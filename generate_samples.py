import numpy as np
import cv2
import pandas as pd
import os

os.makedirs("sample_data", exist_ok=True)

def generate_photorealistic_chest(filename, has_pneumonia=True):
    h, w = 512, 512
    # Base anatomical canvas (dark background)
    scan = np.zeros((h, w), dtype=np.float32) + 22.0

    # Thoracic rib cage outer boundary
    cv2.ellipse(scan, (256, 260), (195, 230), 0, 0, 360, 55.0, -1)

    # Pulmonary lung fields (air is radiolucent / dark)
    cv2.ellipse(scan, (170, 250), (65, 140), -8, 0, 360, 18.0, -1)
    cv2.ellipse(scan, (342, 250), (65, 140), 8, 0, 360, 18.0, -1)

    # Mediastinum and cardiac silhouette (heart shadow tilted left)
    cv2.ellipse(scan, (256, 220), (32, 180), 0, 0, 360, 80.0, -1)
    cv2.ellipse(scan, (280, 290), (65, 55), -20, 0, 360, 95.0, -1)

    # Clavicles (collarbones)
    cv2.line(scan, (95, 120), (220, 145), 110.0, 10)
    cv2.line(scan, (417, 120), (292, 145), 110.0, 10)

    # Posterior & anterior ribs
    for y_offset in range(170, 390, 32):
        cv2.ellipse(scan, (256, y_offset), (185, 28), 0, 20, 160, 85.0, 7)

    # Anatomical vascular textures & noise
    noise = np.random.normal(0, 7, (h, w)).astype(np.float32)
    scan += noise

    # Simulated alveolar pneumonia consolidation (dense white patchy infiltrates)
    if has_pneumonia:
        cv2.circle(scan, (335, 285), 45, 135.0, -1)
        cv2.ellipse(scan, (355, 320), (35, 25), 15, 0, 360, 125.0, -1)

    # Gaussian blur to simulate radiological scatter
    scan = cv2.GaussianBlur(scan, (17, 17), 0)
    scan = np.clip(scan, 0, 255).astype(np.uint8)

    cv2.imwrite(os.path.join("sample_data", filename), scan)
    print(f"Generated realistic radiograph: sample_data/{filename}")

# Generate demo radiographs
generate_photorealistic_chest("sample_chest.png", has_pneumonia=True)
generate_photorealistic_chest("normal_chest.png", has_pneumonia=False)

# Generate 187-point ECG heartbeat row
t = np.linspace(0, 1, 187)
p_wave = 0.15 * np.exp(-((t - 0.2) ** 2) / (2 * 0.02 ** 2))
qrs_wave = 1.0 * np.exp(-((t - 0.45) ** 2) / (2 * 0.015 ** 2)) - 0.2 * np.exp(-((t - 0.42) ** 2) / (2 * 0.008 ** 2))
t_wave = 0.3 * np.exp(-((t - 0.7) ** 2) / (2 * 0.04 ** 2))
noise = np.random.normal(0, 0.015, 187)
synthetic_ecg = np.clip(p_wave + qrs_wave + t_wave + noise, 0, 1)

df = pd.DataFrame([synthetic_ecg])
df.to_csv("sample_data/sample_ecg.csv", header=False, index=False)
print("Generated ECG beat: sample_data/sample_ecg.csv")