import torch
import torch.nn as nn
import numpy as np
import cv2
from PIL import Image
import torchxrayvision as xrv  # type: ignore

class XRayDiagnosisEngine:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load a DenseNet121 pre-trained on multiple clinical X-ray datasets
        self.model = xrv.models.DenseNet(weights="densenet121-res224-all")
        self.model.to(self.device)
        self.model.eval()

        # Extract the 18 specific clinical pathologies the model is trained to detect
        self.classes = self.model.pathologies

        # Hook storage for Grad-CAM
        self.gradients = None
        self.activations = None
        self._register_hooks()

    def _register_hooks(self):
        # Target the final normalization layer of DenseNet features for Grad-CAM
        target_layer = self.model.features.norm5

        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_in, grad_out):
            self.gradients = grad_out[0].detach()

        target_layer.register_forward_hook(forward_hook)
        target_layer.register_full_backward_hook(backward_hook)

    def process_and_explain(self, pil_image):
        """
        Runs forward inference using TorchXRayVision and computes Grad-CAM attention.
        """
        self.model.zero_grad()
        
        # 1. Medical Preprocessing: X-rays are typically single-channel grayscale
        img_np = np.array(pil_image.convert("L"))
        
        # TorchXRayVision normalizes 8-bit images to a [-1024, 1024] scale
        img_norm = xrv.datasets.normalize(img_np, 255) 
        
        # Resize to 224x224 and format to tensor: (Batch, Channel, H, W)
        img_resized = cv2.resize(img_norm, (224, 224), interpolation=cv2.INTER_AREA)
        input_tensor = torch.from_numpy(img_resized).unsqueeze(0).unsqueeze(0).float().to(self.device)
        input_tensor.requires_grad = True

        # 2. Forward pass
        logits = self.model(input_tensor)
        
        # XRV models use independent sigmoid activations for multi-label classification
        probs = torch.sigmoid(logits)[0]
        
        # Get the pathology with the highest probability
        pred_idx = torch.argmax(probs).item()
        confidence = probs[pred_idx].item()
        diagnosis = self.classes[pred_idx]

        # 3. Backward pass for Grad-CAM
        score = logits[0, pred_idx]
        score.backward()

        # Global Average Pooling of gradients
        pooled_grads = torch.mean(self.gradients, dim=[0, 2, 3])
        activations = self.activations[0]

        # Weight the feature maps by the gradients
        for i in range(activations.shape[0]):
            activations[i, :, :] *= pooled_grads[i]

        heatmap = torch.mean(activations, dim=0).cpu().numpy()
        heatmap = np.maximum(heatmap, 0)  # ReLU
        
        if np.max(heatmap) > 0:
            heatmap /= np.max(heatmap)

        # 4. Colorize and blend the heatmap
        w, h = pil_image.size
        heatmap_resized = cv2.resize(heatmap, (w, h))

        heatmap_uint8 = np.uint8(255 * heatmap_resized)
        heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        # Filter out low-attention areas to make the visual cleaner
        heatmap_filtered = np.where(heatmap_resized > 0.35, heatmap_resized, 0)

        return diagnosis, confidence, heatmap_colored, heatmap_filtered