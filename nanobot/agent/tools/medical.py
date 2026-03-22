"""Medical imaging tool for agent integration."""

from __future__ import annotations

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class MedicalPerceptionTool(Tool):
    """Tool for perceiving and analyzing 3D medical images."""

    @property
    def name(self) -> str:
        return "perceive_medical_volume"

    @property
    def description(self) -> str:
        return (
            "Load and analyze a 3D medical image (DICOM series or NIfTI file). "
            "Extracts metadata (dimensions, spacing) and generates orthogonal triplane "
            "views (axial, coronal, sagittal) at the center of the volume. "
            "Returns a preview image and metadata suitable for visual analysis."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "volume_path": {
                    "type": "string",
                    "description": "Path to the medical image file (NIfTI .nii/.nii.gz) or directory containing DICOM series",
                },
            },
            "required": ["volume_path"],
        }

    async def execute(self, volume_path: str) -> str:
        """Execute the medical perception tool.

        Args:
            volume_path: Path to the medical image file or directory.

        Returns:
            JSON string with metadata and preview path, or error.
            The preview image path can be used by the agent to load the image via media.
        """
        from nanobot.medical.dicom.perception_reader import perceive_medical_volume

        result = perceive_medical_volume(volume_path)

        if result.get("error"):
            return json.dumps({"error": result["error"]}, indent=2)

        # Return result with preview_image_path marked for extraction
        return json.dumps({
            "metadata": result["metadata"],
            "preview_image_path": result["preview_path"],
            "message": f"Medical image processed. Preview saved to: {result['preview_path']}"
        }, indent=2)
