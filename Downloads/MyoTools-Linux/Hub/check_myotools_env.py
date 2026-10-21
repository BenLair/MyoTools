#!/usr/bin/env python3
"""Smoke-check a MyoSeg + MyoClass (Cellpose 3) environment.

Usage:
    python check_myoseg_myoclass_env.py
    python check_myoseg_myoclass_env.py --gui  # requires a local desktop display

This validates imports, expected APIs, and synthetic napari layers. It cannot
validate real inference without the custom Cellpose models and example images.
"""

import argparse
import importlib
import inspect
import sys
from importlib.metadata import PackageNotFoundError, version

import numpy as np


def package_version(distribution):
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "MISSING"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="Open a synthetic napari viewer")
    args = parser.parse_args()

    names = (
        "cellpose", "napari", "aicsimageio", "aicspylibczi", "tifffile",
        "numpy", "torch", "qtpy", "PySide6", "pandas", "scipy", "scikit-image",
        "Pillow", "zarr", "numcodecs", "fsspec", "opencv-python-headless",
        "voila", "ipywidgets", "ipyfilechooser", "openpyxl",
    )
    print("Python:", sys.version.split()[0], "\nExecutable:", sys.executable)
    for name in names:
        print(f"  {name:25s}: {package_version(name)}")

    assert sys.version_info[:2] == (3, 11), "Expected Python 3.11"
    assert package_version("cellpose").startswith("3."), "Cellpose 3 is required"
    assert np.__version__ == "1.26.4", "Expected pinned NumPy 1.26.4"

    # Validate all extra imports used by the notebooks/reviewer.
    import pandas as pd
    import scipy.ndimage
    import scipy.spatial
    import skimage.measure
    import skimage.segmentation
    import skimage.transform
    import tifffile as tiff
    import zarr
    import numcodecs
    import openpyxl
    import ipywidgets
    from ipyfilechooser import FileChooser
    from aicsimageio import AICSImage
    from aicspylibczi import CziFile
    from PIL import Image
    from IPython.display import display
    from cellpose import models
    import torch

    required_constructor = {"gpu", "pretrained_model", "model_type"}
    actual_constructor = set(inspect.signature(models.CellposeModel).parameters)
    assert required_constructor <= actual_constructor, (
        f"CellposeModel API mismatch: {required_constructor - actual_constructor}"
    )
    required_eval = {
        "channels", "diameter", "flow_threshold", "cellprob_threshold",
        "min_size", "batch_size", "normalize", "resample",
    }
    actual_eval = set(inspect.signature(models.CellposeModel.eval).parameters)
    assert required_eval <= actual_eval, (
        f"CellposeModel.eval API mismatch: {required_eval - actual_eval}"
    )

    # Import Qt and validate names used by the actual embedded reviewer.
    import napari
    from qtpy import API_NAME
    from qtpy.QtCore import Qt, QObject, QEvent
    from qtpy.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QComboBox, QCheckBox, QSlider, QFileDialog, QMessageBox,
    )
    assert hasattr(Qt, "Horizontal"), "Reviewer relies on Qt.Horizontal"
    for name in ("Save", "Discard", "Cancel"):
        assert hasattr(QMessageBox, name), f"Reviewer relies on QMessageBox.{name}"
    print("Qt backend:", API_NAME)
    assert API_NAME.lower() == "pyside6", f"Expected PySide6, got {API_NAME}"
    print("PyTorch:", torch.__version__)
    print("PyTorch CUDA build:", torch.version.cuda)
    print("CUDA available:", torch.cuda.is_available())
    assert torch.version.cuda is not None, (
        "A CPU-only PyTorch wheel was installed. Expected torch==2.10.0+cu126 "
        "for generic CUDA-enabled installation with CPU fallback."
    )
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
    else:
        print("CPU fallback is expected on computers without compatible NVIDIA CUDA hardware/driver.")

    # These layer calls do not need a displayed window or OpenGL context.
    from napari.layers import Points, Labels
    points = Points(
        np.array([[10.0, 20.0], [40.0, 50.0]]),
        features={"type": np.array(["0", "1"]), "label_id": np.array([1, 2])},
        size=25, face_color="red", text={"string": "{type}", "color": "white", "size": 14},
    )
    points.shown = np.array([True, False])
    points.selected_data = {0}
    points.text = {"string": "{label_id}: {type}", "color": "white", "size": 14}
    labels = Labels(np.zeros((64, 64), dtype=np.int32))
    labels.contour = 1
    labels.editable = False
    print("PASS: core imports, CZI reader imports, Cellpose 3 API, reviewer layer API")

    if args.gui:
        print("Launching desktop napari smoke test: close the window when finished.")
        viewer = napari.Viewer(title="MyoSeg + MyoClass environment smoke test")
        viewer.add_image(np.random.default_rng(1).random((64, 64)), name="Synthetic fluorescence")
        viewer.add_labels(np.zeros((64, 64), dtype=np.int32), name="Reference mask")
        viewer.add_points(
            [[10.0, 20.0], [40.0, 50.0]],
            features={"type": np.array(["0", "1"])},
            size=15,
            text={"string": "{type}", "color": "white", "size": 14},
        )
        napari.run()


if __name__ == "__main__":
    main()
