"""Medical imaging perception reader for DICOM and NIfTI files.

This module provides functionality to read 3D medical images, extract metadata,
and generate orthogonal triplane views (axial, coronal, sagittal) for VLM perception.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image


def _filter_dicom_images(file_paths: list[str]) -> list[str]:
    """Filter DICOM files to include only image types.

    This filters out non-image DICOM types such as:
    - RT Structure Sets (RTSS)
    - RT Plans
    - RT Dose
    - Segmentation objects
    - Presentation states
    - etc.

    Args:
        file_paths: List of DICOM file paths.

    Returns:
        Filtered list containing only image DICOM files.
    """
    import SimpleITK as sitk

    image_files = []

    for f in file_paths:
        try:
            # Read only the header to check SOP Class UID
            reader = sitk.ImageFileReader()
            reader.SetFileName(f)
            reader.SetExtractMetaDataOnly(True)
            reader.Execute()

            # Get SOP Class UID
            sop_class = reader.GetMetaData("0008|0016")

            # Filter out non-image SOP Classes
            # Image Storage SOP Classes typically end with "Storage"
            # Non-image classes: RT Structure Set, RT Plan, RT Dose, etc.

            # Known non-image SOP Class UIDs to exclude
            non_image_classes = {
                "1.2.840.10008.5.1.4.1.1.481.1",  # RT Structure Set Storage
                "1.2.840.10008.5.1.4.1.1.481.2",  # RT Plan Storage
                "1.2.840.10008.5.1.4.1.1.481.3",  # RT Dose Storage
                "1.2.840.10008.5.1.4.1.1.481.4",  # RT Treatment Summary Record
                "1.2.840.10008.5.1.4.1.1.66",     # Segmentation Storage
                "1.2.840.10008.5.1.4.1.1.11.1",   # Grayscale Softcopy Presentation State
                "1.2.840.10008.5.1.4.1.1.66.4",   # Surface Segmentation
                "1.2.840.10008.5.1.4.1.1.88.67",  # Radiopharmaceutical Radiation Dose SR
            }

            # Check if this is a known non-image DICOM
            # If sop_class is None/empty, we treat it as potentially an image
            # (conservative approach - only skip if explicitly known non-image)
            is_non_image = False
            if sop_class:
                sop_class = sop_class.strip()
                if sop_class in non_image_classes:
                    is_non_image = True

            if is_non_image:
                continue  # Skip non-image DICOM

            # If we get here, treat as image file
            image_files.append(f)

        except Exception:
            # If we can't read metadata, try reading the actual image
            # Some DICOM files have metadata that can't be read with
            # SetExtractMetaDataOnly but are still valid images
            try:
                test_image = sitk.ReadImage(f)
                # If we can read it, it's a valid image
                image_files.append(f)
            except Exception:
                # Can't read as image either, skip it
                pass

    return image_files


def load_medical_image(path: str) -> Any:
    """Load a medical image from DICOM series or NIfTI file.

    Args:
        path: Path to the medical image file or directory containing DICOM series.

    Returns:
        SimpleITK Image object.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the file cannot be loaded.
    """
    import SimpleITK as sitk
    from pathlib import Path

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    try:
        if path_obj.is_dir():
            # DICOM series - use ImageSeriesReader
            reader = sitk.ImageSeriesReader()
            # Get all DICOM files in the directory
            all_dicom_files = reader.GetGDCMSeriesFileNames(str(path))

            if not all_dicom_files:
                raise RuntimeError(f"No DICOM series found in directory: {path}")

            # Filter out non-image DICOM files (RTSS, RT Plan, etc.)
            dicom_files = _filter_dicom_images(list(all_dicom_files))

            if not dicom_files:
                raise RuntimeError(f"No DICOM image files found in directory: {path} (found {len(all_dicom_files)} non-image DICOM files)")

            reader.SetFileNames(dicom_files)
            image = reader.Execute()
        else:
            # Single file (NIfTI or single DICOM)
            image = sitk.ReadImage(str(path))
        return image
    except Exception as e:
        raise RuntimeError(f"Failed to load medical image: {e}")


def extract_metadata(image: Any) -> dict[str, Any]:
    """Extract metadata from a medical image.

    Args:
        image: SimpleITK Image object.

    Returns:
        Dictionary containing dimensions, spacing, origin, and direction.
    """
    size = image.GetSize()
    spacing = image.GetSpacing()
    origin = image.GetOrigin()
    direction = image.GetDirection()

    return {
        "dimensions": {
            "x": size[0],
            "y": size[1],
            "z": size[2],
        },
        "spacing": {
            "x": spacing[0],
            "y": spacing[1],
            "z": spacing[2],
        },
        "origin": {
            "x": origin[0],
            "y": origin[1],
            "z": origin[2],
        },
        "direction": list(direction),
        "size_mm": {
            "x": size[0] * spacing[0],
            "y": size[1] * spacing[1],
            "z": size[2] * spacing[2],
        },
    }


def extract_triplane_views(array: np.ndarray) -> dict[str, np.ndarray]:
    """Extract orthogonal triplane views from a 3D array.

    Args:
        array: 3D numpy array with shape (Z, Y, X).

    Returns:
        Dictionary with 'axial', 'coronal', and 'sagittal' slices.
    """
    z_dim, y_dim, x_dim = array.shape

    # Calculate center indices
    z_mid = z_dim // 2
    y_mid = y_dim // 2
    x_mid = x_dim // 2

    # Extract slices
    # Axial (transverse) - looking from top/bottom
    axial = array[z_mid, :, :]

    # Coronal - looking from front/back
    coronal = array[:, y_mid, :]

    # Sagittal - looking from left/right
    sagittal = array[:, :, x_mid]

    return {
        "axial": axial,
        "coronal": coronal,
        "sagittal": sagittal,
    }


def apply_aspect_ratio_correction(
    slices: dict[str, np.ndarray],
    spacing: dict[str, float],
) -> dict[str, np.ndarray]:
    """Apply aspect ratio correction based on physical spacing.

    Args:
        slices: Dictionary of slice arrays.
        spacing: Dictionary with 'x', 'y', 'z' spacing values.

    Returns:
        Dictionary with resized slices.
    """
    corrected = {}

    # Axial plane: X and Y axes (typically isotropic in modern scanners)
    axial = slices["axial"]
    corrected["axial"] = axial  # Usually no correction needed

    # Coronal plane: X (horizontal) and Z (vertical)
    # Height needs to be scaled by Z spacing relative to X spacing
    coronal = slices["coronal"]
    if spacing["z"] != spacing["x"]:
        # Resize to correct aspect ratio
        new_height = int(coronal.shape[0] * spacing["z"] / spacing["x"])
        new_width = coronal.shape[1]
        # Normalize to 0-255 first
        coronal_normalized = normalize_for_display(coronal)
        coronal_pil = Image.fromarray(coronal_normalized)
        coronal_pil = coronal_pil.resize((new_width, new_height), Image.BILINEAR)
        coronal = np.array(coronal_pil)
    corrected["coronal"] = coronal

    # Sagittal plane: Y (horizontal) and Z (vertical)
    # Height needs to be scaled by Z spacing relative to Y spacing
    sagittal = slices["sagittal"]
    if spacing["z"] != spacing["y"]:
        new_height = int(sagittal.shape[0] * spacing["z"] / spacing["y"])
        new_width = sagittal.shape[1]
        # Normalize to 0-255 first
        sagittal_normalized = normalize_for_display(sagittal)
        sagittal_pil = Image.fromarray(sagittal_normalized)
        sagittal_pil = sagittal_pil.resize((new_width, new_height), Image.BILINEAR)
        sagittal = np.array(sagittal_pil)
    corrected["sagittal"] = sagittal

    return corrected


def normalize_for_display(array: np.ndarray) -> np.ndarray:
    """Normalize array to uint8 range [0, 255] using percentile-based scaling.

    Args:
        array: Input array (can be any numeric type).

    Returns:
        Normalized uint8 array.
    """
    if array.size == 0:
        return np.zeros_like(array, dtype=np.uint8)

    # Use percentiles to avoid outliers affecting the range
    p1 = np.percentile(array, 1)
    p99 = np.percentile(array, 99)

    if p99 <= p1:
        # Constant image
        return np.full_like(array, 128, dtype=np.uint8)

    # Clip and scale to 0-255
    clipped = np.clip(array, p1, p99)
    normalized = ((clipped - p1) / (p99 - p1) * 255).astype(np.uint8)

    return normalized


def normalize_and_concatenate(
    slices: dict[str, np.ndarray],
    separator_width: int = 10,
) -> Image.Image:
    """Normalize slices and concatenate them horizontally with separators.

    Args:
        slices: Dictionary of slice arrays.
        separator_width: Width of the white separator between slices.

    Returns:
        Concatenated PIL Image.
    """
    # Normalize all slices
    normalized = {
        name: normalize_for_display(arr) for name, arr in slices.items()
    }

    # Convert to PIL Images
    images = []
    for name in ["axial", "coronal", "sagittal"]:
        if name in normalized:
            img = Image.fromarray(normalized[name])
            # Ensure grayscale is converted to RGB for consistency
            if img.mode == 'L':
                img = img.convert('RGB')
            images.append(img)

    if not images:
        raise ValueError("No valid images to concatenate")

    # Find the maximum height
    max_height = max(img.height for img in images)

    # Resize all images to the same height if needed
    resized_images = []
    for img in images:
        if img.height != max_height:
            ratio = max_height / img.height
            new_width = int(img.width * ratio)
            img = img.resize((new_width, max_height), Image.BILINEAR)
        resized_images.append(img)

    # Create white separator
    separator = Image.new('RGB', (separator_width, max_height), color=(255, 255, 255))

    # Concatenate images with separators
    result = resized_images[0]
    for img in resized_images[1:]:
        # Create new image with space for separator and next image
        new_width = result.width + separator_width + img.width
        new_img = Image.new('RGB', (new_width, max_height), color=(255, 255, 255))
        new_img.paste(result, (0, 0))
        new_img.paste(separator, (result.width, 0))
        new_img.paste(img, (result.width + separator_width, 0))
        result = new_img

    return result


def perceive_medical_volume(path: str) -> dict[str, Any]:
    """Main entry point for medical volume perception.

    Loads a medical image, extracts metadata, generates triplane views,
    and creates a concatenated preview image.

    Args:
        path: Path to the medical image file or directory.

    Returns:
        Dictionary containing:
        - metadata: Image metadata (dimensions, spacing, etc.)
        - preview_path: Path to the generated preview image
        - error: Error message if something went wrong
    """
    import base64
    from pathlib import Path
    import tempfile

    import SimpleITK as sitk

    try:
        # Load the medical image
        image = load_medical_image(path)

        # Extract metadata
        metadata = extract_metadata(image)

        # Convert to numpy array
        array = sitk.GetArrayFromImage(image)

        # Extract triplane views
        slices = extract_triplane_views(array)

        # Apply aspect ratio correction
        spacing = metadata["spacing"]
        slices_corrected = apply_aspect_ratio_correction(slices, spacing)

        # Normalize and concatenate
        preview = normalize_and_concatenate(slices_corrected)

        # Save preview to temporary file
        preview_path = Path(tempfile.gettempdir()) / f"medical_preview_{hash(path) % 10000:04d}.png"
        preview.save(str(preview_path), "PNG")

        return {
            "metadata": metadata,
            "preview_path": str(preview_path),
            "error": None,
        }

    except FileNotFoundError as e:
        return {"error": f"File not found: {e}"}
    except RuntimeError as e:
        return {"error": f"Failed to process image: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


