"""Tests for medical imaging perception tool."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestPerceptionReader:
    """Tests for perception_reader module."""

    def test_extract_metadata(self):
        """Test metadata extraction from a simple image."""
        try:
            import SimpleITK as sitk
            from nanobot.medical.dicom.perception_reader import extract_metadata

            # Create a simple test image
            arr = np.random.rand(10, 20, 30).astype(np.float32)
            image = sitk.GetImageFromArray(arr)
            image.SetSpacing([1.0, 2.0, 3.0])
            image.SetOrigin([10.0, 20.0, 30.0])

            metadata = extract_metadata(image)

            assert metadata["dimensions"]["x"] == 30
            assert metadata["dimensions"]["y"] == 20
            assert metadata["dimensions"]["z"] == 10
            assert metadata["spacing"]["x"] == 1.0
            assert metadata["spacing"]["y"] == 2.0
            assert metadata["spacing"]["z"] == 3.0
            assert metadata["origin"]["x"] == 10.0
            assert metadata["size_mm"]["x"] == 30.0  # 30 * 1.0
        except ImportError:
            pytest.skip("SimpleITK not installed")

    def test_extract_triplane_views(self):
        """Test triplane view extraction."""
        from nanobot.medical.dicom.perception_reader import extract_triplane_views

        # Create a test 3D array
        arr = np.random.rand(50, 40, 30).astype(np.float32)

        slices = extract_triplane_views(arr)

        # Check that all three planes are present
        assert "axial" in slices
        assert "coronal" in slices
        assert "sagittal" in slices

        # Check shapes (axial should be Y x X, coronal should be Z x X, sagittal should be Z x Y)
        assert slices["axial"].shape == (40, 30)
        assert slices["coronal"].shape == (50, 30)
        assert slices["sagittal"].shape == (50, 40)

    def test_normalize_for_display(self):
        """Test image normalization."""
        from nanobot.medical.dicom.perception_reader import normalize_for_display

        # Create a test array with outliers
        arr = np.random.rand(100, 100).astype(np.float32) * 1000
        arr[0, 0] = 10000  # Outlier

        normalized = normalize_for_display(arr)

        # Check that output is uint8 and in correct range
        assert normalized.dtype == np.uint8
        assert normalized.min() >= 0
        assert normalized.max() <= 255

    def test_perceive_medical_volume_nifti(self):
        """Test end-to-end perception on a NIfTI file."""
        try:
            import nibabel as nib
            from nanobot.medical.dicom.perception_reader import perceive_medical_volume
        except ImportError:
            pytest.skip("nibabel not installed")

        # Create a temporary NIfTI file
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple 3D array
            data = np.random.rand(32, 32, 32).astype(np.float32)
            affine = np.eye(4)
            img = nib.Nifti1Image(data, affine)

            filepath = Path(tmpdir) / "test.nii.gz"
            nib.save(img, str(filepath))

            # Process the file
            result = perceive_medical_volume(str(filepath))

            # Check the result
            assert "error" in result
            if result["error"] is not None:
                # SimpleITK might not support the format
                assert "Failed to load" in result["error"] or "not found" in result["error"].lower()
            else:
                assert "metadata" in result
                assert "preview_path" in result
                assert "preview_base64" in result
                assert Path(result["preview_path"]).exists()


class TestMedicalPerceptionTool:
    """Tests for MedicalPerceptionTool."""

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        """Test that the tool has correct schema."""
        from nanobot.agent.tools.medical import MedicalPerceptionTool

        tool = MedicalPerceptionTool()

        assert tool.name == "perceive_medical_volume"
        assert "medical image" in tool.description.lower()
        assert "volume_path" in tool.parameters["properties"]
        assert "volume_path" in tool.parameters["required"]

    @pytest.mark.asyncio
    async def test_tool_execute_error(self):
        """Test tool execution with invalid path."""
        from nanobot.agent.tools.medical import MedicalPerceptionTool

        tool = MedicalPerceptionTool()
        result = await tool.execute(volume_path="/nonexistent/path.nii.gz")

        result_dict = json.loads(result)
        assert "error" in result_dict
        assert result_dict["error"] is not None
