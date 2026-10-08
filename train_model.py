import torch
import torch.nn as nn
import torchvision
import torchxrayvision as xrv
import os

def main():
    # 1. Setup Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    # 2. Load Medical Transformations
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(224)
    ])

    # 3. Load a Clinical Dataset
    # Using the built-in COVID-19 dataset for a quick local test. 
    # For production, replace this with xrv.datasets.NIH_Dataset(imgpath="path/to/images")
    print("Downloading/Loading clinical dataset...")
    dataset = xrv.datasets.COVID19_Dataset(
        views=["PA", "AP"],
        transform=transform
    )
    
    # We will train on the first 50 images for local testing
    subset_indices = list(range(min(50, len(dataset))))
    subset = torch.utils.data.Subset(dataset, subset_indices)
    dataloader = torch.utils.data.DataLoader(subset, batch_size=8, shuffle=True)

    # 4. Initialize Pre-Trained DenseNet121
    print("Loading pre-trained DenseNet121...")
    model = xrv.models.DenseNet(weights="densenet121-res224-all")

    # Freeze base layers
    for param in model.parameters():
        param.requires_grad = False

    # Replace the classification head (subset of target pathologies)
    num_target_classes = len(dataset.pathologies)
    model.classifier = nn.Linear(model.classifier.in_features, num_target_classes)
    model = model.to(device)

    # 5. Define Loss and Optimizer
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=0.001)

    # 6. Training Loop
    epochs = 3
    print("Starting training loop...")
    model.train()

    for epoch in range(epochs):
        running_loss = 0.0
        for batch in dataloader:
            # xrv datasets return a dict: {'img': tensor, 'lab': tensor}
            images = batch["img"].to(device)
            targets = batch["lab"].to(device)

            optimizer.zero_grad()
            
            outputs = model(images)
            loss = criterion(outputs, targets)
            
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            
        avg_loss = running_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{epochs} Completed - Loss: {avg_loss:.4f}")

    # 7. Save Fine-Tuned Weights
    os.makedirs("models", exist_ok=True)
    save_path = "models/densenet_finetuned.pth"
    torch.save(model.state_dict(), save_path)
    print(f"Training complete. Weights saved to {save_path}")

if __name__ == "__main__":
    main()