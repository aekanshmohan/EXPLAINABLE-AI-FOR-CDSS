import torch
import torch.nn as nn
import numpy as np

class ECG1DCNN(nn.Module):
    def __init__(self, num_classes=5):
        super(ECG1DCNN, self).__init__()
        self.conv1 = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        self.conv2 = nn.Sequential(
            nn.Conv1d(16, 32, kernel_size=5, stride=1, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        self.conv3 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(8)
        )
        self.fc = nn.Sequential(
            nn.Linear(64 * 8, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)

class ECGDiagnosisEngine:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.classes = [
            "Normal Sinus Rhythm (NSR)",
            "Supraventricular Ectopy (SVEB)",
            "Ventricular Ectopic Beat (VEB)",
            "Fusion Beat (FUS)",
            "Unclassifiable / Indeterminate"
        ]
        
        self.model = ECG1DCNN(num_classes=len(self.classes))
        self.model.to(self.device)
        self.model.eval()

    def process_and_explain(self, signal_array):
        """
        Expects a 1D numpy array of length 187.
        Returns diagnosis, confidence, and saliency gradient map.
        """
        signal = np.array(signal_array, dtype=np.float32)
        if len(signal) > 187:
            signal = signal[:187]
        elif len(signal) < 187:
            signal = np.pad(signal, (0, 187 - len(signal)), 'constant')

        # Format to tensor (Batch, Channels, Length)
        tensor = torch.tensor(signal).unsqueeze(0).unsqueeze(0).to(self.device)
        tensor.requires_grad = True

        # Forward pass
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0, pred_idx].item()
        diagnosis = self.classes[pred_idx]

        # Backward pass for temporal saliency
        score = logits[0, pred_idx]
        score.backward()

        # Compute gradient magnitude
        gradients = tensor.grad.data.abs().squeeze().cpu().numpy()
        if np.max(gradients) > 0:
            saliency = (gradients - np.min(gradients)) / (np.max(gradients) - np.min(gradients))
        else:
            saliency = np.zeros_like(gradients)

        return diagnosis, confidence, saliency