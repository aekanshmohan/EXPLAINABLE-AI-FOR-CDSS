import torch
import torch.nn as nn
import torchvision
import torchxrayvision as xrv
from PIL import Image
import numpy as np

# 1. Rebuild the Exact Training Architecture
print("Loading model architecture...")
model = xrv.models.DenseNet(weights="densenet121-res224-all")
model.op_threshs = None        
model.apply_sigmoid = False    

# The NIH dataset tracks these 14 specific pathologies
pathologies = ['Atelectasis', 'Consolidation', 'Infiltration', 'Pneumothorax', 
               'Edema', 'Emphysema', 'Fibrosis', 'Effusion', 'Pneumonia', 
               'Pleural_Thickening', 'Cardiomegaly', 'Nodule', 'Mass', 'Hernia']

# Rebuild the final layer to output 14 classes
model.classifier = nn.Linear(model.classifier.in_features, len(pathologies))

# 2. Load Your Kaggle Weights
print("Loading saved weights...")
model.load_state_dict(torch.load('best_densenet_finetuned.pth', map_location=torch.device('cpu'), weights_only=True))
model.eval() 

# 3. Local Image Preprocessing Pipeline
def process_xray(img_path):
    img = Image.open(img_path).convert('L')
    img = np.array(img)
    
    img = xrv.datasets.normalize(img, 255) 
    img = img[np.newaxis, ...]  
    
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(224)
    ])
    
    img = transform(img)
    return torch.from_numpy(img).unsqueeze(0).float()

# 4. Generate CDSS Predictions
def predict_xray(image_path):
    print(f"\nAnalyzing {image_path}...")
    img_tensor = process_xray(image_path)
    
    with torch.no_grad():
        logits = model(img_tensor)
        probabilities = torch.sigmoid(logits).squeeze().numpy()
        
    print("\n--- Diagnostic Probabilities ---")
    results = {}
    for path, prob in zip(pathologies, probabilities):
        results[path] = prob
        print(f"{path.ljust(20)}: {prob*100:.1f}%")
        
    return results

# --- Test the Model ---
if __name__ == "__main__":
    # Pointing directly to the file in your sample_data folder
    predict_xray('sample_data/sample_chest.png')