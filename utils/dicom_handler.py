import pydicom
from pydicom.pixel_data_handlers.util import apply_voi_lut
import numpy as np
from PIL import Image
import io

def parse_and_deidentify_dicom(file_bytes):
    """
    Parses a DICOM byte stream, extracts non-PHI acquisition metadata,
    and returns a window-leveled 8-bit PIL Image suitable for PyTorch models.
    """
    dcm = pydicom.dcmread(io.BytesIO(file_bytes), force=True)

    # 1. Extract non-PHI acquisition parameters
    metadata = {
        "Modality": getattr(dcm, "Modality", "CR / DX"),
        "Body Part Examined": getattr(dcm, "BodyPartExamined", "CHEST"),
        "Manufacturer": getattr(dcm, "Manufacturer", "Hospital Imaging Modality"),
        "KVP (Tube Voltage)": f"{getattr(dcm, 'KVP', 'N/A')} kVp",
        "Exposure Time": f"{getattr(dcm, 'ExposureTime', 'N/A')} ms",
        "Patient Orientation": str(getattr(dcm, "PatientOrientation", "PA")),
        "Photometric Interpretation": getattr(dcm, "PhotometricInterpretation", "MONOCHROME2")
    }

    # 2. Extract and window-level raw pixel array
    try:
        pixel_array = apply_voi_lut(dcm.pixel_array, dcm)
    except Exception:
        pixel_array = dcm.pixel_array.astype(float)

    # Invert if MONOCHROME1 (where zero is white)
    if metadata["Photometric Interpretation"] == "MONOCHROME1":
        pixel_array = np.amax(pixel_array) - pixel_array

    # Normalize to 0-255 uint8 range
    p_min, p_max = np.min(pixel_array), np.max(pixel_array)
    if p_max > p_min:
        norm_img = ((pixel_array - p_min) / (p_max - p_min) * 255.0).astype(np.uint8)
    else:
        norm_img = np.zeros(pixel_array.shape, dtype=np.uint8)

    pil_img = Image.fromarray(norm_img).convert("RGB")
    return pil_img, metadata