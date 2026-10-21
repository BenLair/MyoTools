"""MyoClass manual review. Launch from Voilà or with --session review_session.json.

Binary marker calls are edited; reference labels and centroid positions stay fixed.
Qt and napari are imported only when opening the desktop editor.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import tifffile as tiff


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save_mapping(path, frame):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.xlsx")
    try:
        frame.to_excel(temp, index=False, sheet_name="mapping", engine="openpyxl")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_mapping(path, entry, automatic=None):
    frame = pd.read_excel(path, sheet_name="mapping", engine="openpyxl")
    channels = [f"ch{c['index']}" for c in entry["channels"]]
    required = ["label_id", "area_px", "y", "x", *channels]
    if not set(required).issubset(frame.columns):
        raise ValueError(f"Mapping is missing columns: {set(required) - set(frame.columns)}")
    ids = pd.to_numeric(frame["label_id"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(ids).all() or not np.equal(ids, np.floor(ids)).all() or (ids <= 0).any():
        raise ValueError("label_id must contain positive integer identifiers.")
    frame["label_id"] = ids.astype(np.int64)
    if frame.label_id.duplicated().any():
        raise ValueError("Duplicate label_id values in mapping.")
    frame = frame.sort_values("label_id").reset_index(drop=True)
    for channel in channels:
        values = pd.to_numeric(frame[channel], errors="raise")
        if not values.isin([0, 1]).all():
            raise ValueError(f"{channel} must contain only 0 and 1, with no missing values.")
        frame[channel] = values.astype(np.uint8)
    if not np.isfinite(frame[["area_px", "x", "y"]].to_numpy(dtype=float)).all():
        raise ValueError("Mapping coordinates and areas must be finite.")
    if automatic is not None:
        if not np.array_equal(frame.label_id, automatic.label_id):
            raise ValueError("Review label IDs differ from the automatic mapping.")
        if not np.allclose(frame[["area_px", "y", "x"]], automatic[["area_px", "y", "x"]], rtol=0, atol=1e-6):
            raise ValueError("Areas or centroid coordinates changed. Only marker calls may be edited.")
    return frame


def get_review_state(entry):
    path = Path(entry["review_path"])
    meta_path = Path(entry["review_meta"])
    if not path.is_file() or not meta_path.is_file():
        return "Missing review"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("automatic_signature") != entry["map_sig"]:
            return "Stale review"
        if meta.get("mapping_hash") != digest_file(path):
            return "Modified outside editor"
        return "Reviewed" if meta.get("reviewed") else "Draft"
    except (OSError, ValueError):
        return "Invalid review metadata"


def initialize_review(entry, reset=False):
    path = Path(entry["review_path"])
    if path.exists() and not reset:
        return
    frame = load_mapping(entry["automatic_path"], entry)
    if path.exists():
        backup = path.parent / "Backups" / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        meta_path = Path(entry["review_meta"])
        if meta_path.exists():
            shutil.copy2(meta_path, backup.with_suffix(".json"))
    save_mapping(path, frame)
    save_json(entry["review_meta"], {
        "automatic_signature": entry["map_sig"], "mapping_hash": digest_file(path),
        "reviewed": False, "saved_utc": datetime.now(timezone.utc).isoformat(),
        "image_id": entry["image_id"]})


class ReviewDocument:
    """File-backed state independent of napari, so corrections can be validated."""
    def __init__(self, entry):
        self.entry = entry
        state = get_review_state(entry)
        if state in ("Stale review", "Missing review", "Invalid review metadata"):
            raise ValueError(f"{state}. Use Reset selected review in MyoClass to create a fresh draft (backs up existing edits).")
        if digest_file(entry["automatic_path"]) != entry["automatic_hash"]:
            raise ValueError("The automatic mapping was modified. Run automatic classification again.")
        self.automatic = load_mapping(entry["automatic_path"], entry)
        self.frame = load_mapping(entry["review_path"], entry, self.automatic)
        self.expected_hash = digest_file(entry["review_path"])
        self.channels = [f"ch{c['index']}" for c in entry["channels"]]
        self.dirty = False
        self.was_reviewed = state == "Reviewed"

    @property
    def points(self):
        return self.frame[["y", "x"]].to_numpy(dtype=float)

    def set_types(self, channel, indices, value):
        if channel not in self.channels or value not in (0, 1):
            raise ValueError("Select a valid marker and a binary class (0 or 1).")
        indices = np.asarray(sorted(set(indices)), dtype=int)
        if len(indices) and (indices.min() < 0 or indices.max() >= len(self.frame)):
            raise ValueError("Invalid point selection.")
        if len(indices) and (self.frame.loc[indices, channel] != value).any():
            self.frame.loc[indices, channel] = value
            self.dirty = True

    def save(self, reviewed=False):
        path = Path(self.entry["review_path"])
        if digest_file(path) != self.expected_hash:
            raise RuntimeError("This review file changed in another window. Close this editor and reload it before saving.")
        if self.dirty:
            backup = path.parent / "Backups" / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
        final_reviewed = reviewed or (self.was_reviewed and not self.dirty)
        save_mapping(path, self.frame)
        self.expected_hash = digest_file(path)
        save_json(self.entry["review_meta"], {
            "automatic_signature": self.entry["map_sig"], "mapping_hash": self.expected_hash,
            "reviewed": final_reviewed, "saved_utc": datetime.now(timezone.utc).isoformat(),
            "image_id": self.entry["image_id"], "channels": self.channels})
        self.dirty = False
        self.was_reviewed = final_reviewed


def launch_editor(session_path=None, selected_id=None):
    import napari
    from qtpy.QtCore import Qt, QObject, QEvent
    from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QCheckBox, QSlider, QFileDialog, QMessageBox)

    viewer = napari.Viewer(title="MyoClass · manual fiber typing")
    if not session_path:
        session_path, _ = QFileDialog.getOpenFileName(None, "Select a MyoClass review_session.json", "", "MyoClass session (*.json)")
        if not session_path:
            viewer.close()
            return
    payload = json.loads(Path(session_path).read_text(encoding="utf-8"))
    entries = payload["entries"]
    if not entries:
        raise ValueError("This review session has no valid classified images.")

    class Editor:
        def __init__(self):
            self.doc = None
            self.points_layer = None
            self.marker_images = {}
            self.current_channel = None
            self.restoring = False
            panel = QWidget()
            layout = QVBoxLayout(panel)
            layout.addWidget(QLabel("MyoClass · fluorescence marker review"))
            self.image_combo = QComboBox()
            for entry in entries:
                self.image_combo.addItem(f"{entry['filename']} · scene {entry['scene'] + 1}", entry["image_id"])
            layout.addWidget(self.image_combo)
            nav = QHBoxLayout()
            previous = QPushButton("Previous")
            following = QPushButton("Next")
            previous.clicked.connect(lambda: self.navigate(-1))
            following.clicked.connect(lambda: self.navigate(1))
            nav.addWidget(previous); nav.addWidget(following)
            layout.addLayout(nav)
            layout.addWidget(QLabel("Marker to edit (each marker is independent):"))
            self.channel_combo = QComboBox()
            layout.addWidget(self.channel_combo)
            self.show_all = QCheckBox("Show all fluorescence channels")
            self.show_all.stateChanged.connect(self.apply_image_visibility)
            layout.addWidget(self.show_all)
            layout.addWidget(QLabel("Visible points:"))
            self.filter_combo = QComboBox()
            self.filter_combo.addItems(["All", "Negative (0)", "Positive (1)"])
            self.filter_combo.currentIndexChanged.connect(self.refresh_points)
            layout.addWidget(self.filter_combo)
            actions = QHBoxLayout()
            zero, one = QPushButton("F1 · negative (0)"), QPushButton("F2 · positive (1)")
            zero.clicked.connect(lambda: self.set_type(0))
            one.clicked.connect(lambda: self.set_type(1))
            actions.addWidget(zero); actions.addWidget(one)
            layout.addLayout(actions)
            self.show_ids = QCheckBox("Show fiber label IDs")
            self.show_ids.stateChanged.connect(self.refresh_points)
            layout.addWidget(self.show_ids)
            layout.addWidget(QLabel("Point size"))
            self.point_size = QSlider(Qt.Horizontal)
            self.point_size.setRange(3, 150); self.point_size.setValue(25)
            self.point_size.valueChanged.connect(self.refresh_points)
            layout.addWidget(self.point_size)
            layout.addWidget(QLabel("Text size"))
            self.text_size = QSlider(Qt.Horizontal)
            self.text_size.setRange(6, 60); self.text_size.setValue(14)
            self.text_size.valueChanged.connect(self.refresh_points)
            layout.addWidget(self.text_size)
            save_row = QHBoxLayout()
            save = QPushButton("Save draft (Ctrl+S)")
            done = QPushButton("Mark image reviewed")
            save.clicked.connect(lambda: self.save(False))
            done.clicked.connect(lambda: self.save(True))
            save_row.addWidget(save); save_row.addWidget(done)
            layout.addLayout(save_row)
            self.status = QLabel()
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            help_label = QLabel("Select one or several centroids, then press F1 or F2.\nMarker calls are independent; hybrids are allowed.\nReview any inferred category after changing other markers.\nCentroid positions and label masks stay fixed.\nSave drafts while editing; mark reviewed when all markers are checked.")
            help_label.setWordWrap(True)
            layout.addWidget(help_label)
            viewer.window.add_dock_widget(panel, name="MyoClass review", area="left")
            self.image_combo.currentIndexChanged.connect(self.load_image)
            self.channel_combo.currentIndexChanged.connect(self.change_channel)
            index = next((i for i, entry in enumerate(entries) if entry["image_id"] == selected_id), 0)
            self.image_combo.blockSignals(True); self.image_combo.setCurrentIndex(index); self.image_combo.blockSignals(False)
            self.load_image(index)
            for owner in (viewer,):
                owner.bind_key("F1", lambda _: self.set_type(0), overwrite=True)
                owner.bind_key("F2", lambda _: self.set_type(1), overwrite=True)
                owner.bind_key("Control-S", lambda _: self.save(False), overwrite=True)
                owner.bind_key("s", lambda _: self.save(False), overwrite=True)

        def save(self, reviewed=False):
            if self.doc is None:
                return False
            try:
                self.doc.save(reviewed)
                self.update_status()
                return True
            except Exception as exc:
                QMessageBox.critical(None, "Cannot save review", str(exc))
                return False

        def update_status(self):
            if self.doc:
                state = "Unsaved changes" if self.doc.dirty else get_review_state(self.doc.entry)
                marker = self.current_channel or ""
                self.status.setText(f"{state} · {len(self.doc.frame)} fibers · {marker}\n{self.doc.entry['review_path']}")

        def load_image(self, index):
            if self.doc is not None and self.doc.dirty and not self.save(False):
                self.image_combo.blockSignals(True)
                old = next(i for i,e in enumerate(entries) if e['image_id'] == self.doc.entry['image_id'])
                self.image_combo.setCurrentIndex(old); self.image_combo.blockSignals(False)
                return
            try:
                doc = ReviewDocument(entries[index])
                mask = tiff.imread(doc.entry["reference_path"])
                expected = np.unique(mask); expected = expected[expected > 0]
                if not np.array_equal(expected, doc.frame.label_id.to_numpy()):
                    raise ValueError("Reference mask label IDs do not match the mapping.")
                self.doc = doc
                self.points_layer = None
                viewer.layers.clear()
                self.marker_images = {}
                for spec in doc.entry["channels"]:
                    channel = f"ch{spec['index']}"
                    file = doc.entry["prepared_paths"].get(channel)
                    if file:
                        plane = tiff.imread(file)
                        if plane.shape != mask.shape:
                            raise ValueError(f"{channel}: fluorescence and reference mask shapes differ.")
                        self.marker_images[channel] = viewer.add_image(plane, name=f"{channel} · {spec['name']}", colormap="gray", visible=False)
                labels = viewer.add_labels(mask, name="Reference fiber boundaries", opacity=.5)
                labels.contour = 1
                labels.editable = False
                channel = f"ch{doc.entry['channels'][0]['index']}"
                self.current_channel = channel
                features = {"type": doc.frame[channel].astype(str).to_numpy(), "label_id": doc.frame.label_id.to_numpy()}
                self.points_layer = viewer.add_points(doc.points, features=features, size=self.point_size.value(),
                                                      name="Fiber calls · select and press F1/F2",
                                                      face_color="red", text={"string": "{type}", "color": "white", "size": self.text_size.value()})
                self.points_layer.mode = "select"
                self.points_layer.events.data.connect(self.restore_points)
                for key, callback in [("F1",lambda _:self.set_type(0)),("F2",lambda _:self.set_type(1)),
                                      ("Control-S",lambda _:self.save(False)),("s",lambda _:self.save(False))]:
                    self.points_layer.bind_key(key, callback, overwrite=True)
                self.channel_combo.blockSignals(True)
                self.channel_combo.clear()
                for spec in doc.entry["channels"]:
                    suffix = " (inferred category)" if spec.get("derived") else ""
                    self.channel_combo.addItem(f"ch{spec['index']} · {spec['name']}{suffix}", f"ch{spec['index']}")
                self.channel_combo.setCurrentIndex(0); self.channel_combo.blockSignals(False)
                self.refresh_points()
                self.apply_image_visibility()
                viewer.reset_view()
            except Exception as exc:
                QMessageBox.critical(None, "Cannot load image", str(exc))

        def restore_points(self, _=None):
            if self.restoring or self.doc is None or self.points_layer is None:
                return
            if self.points_layer.data.shape != self.doc.points.shape or not np.allclose(self.points_layer.data, self.doc.points):
                self.restoring = True
                try:
                    self.points_layer.data = self.doc.points
                    self.refresh_points()
                finally:
                    self.restoring = False

        def change_channel(self, _=None):
            if not self.doc or self.channel_combo.currentIndex() < 0:
                return
            if self.doc.dirty and not self.save(False):
                self.channel_combo.blockSignals(True)
                self.channel_combo.setCurrentIndex(self.doc.channels.index(self.current_channel))
                self.channel_combo.blockSignals(False)
                return
            self.current_channel = self.channel_combo.currentData()
            self.refresh_points(); self.apply_image_visibility()

        def apply_image_visibility(self, *_):
            for channel, layer in self.marker_images.items():
                layer.visible = self.show_all.isChecked() or channel == self.current_channel

        def refresh_points(self, *_):
            if self.points_layer is None or self.doc is None:
                return
            values = self.doc.frame[self.current_channel].to_numpy(dtype=int)
            layer = self.points_layer
            layer.features = {"type": values.astype(str), "label_id": self.doc.frame.label_id.to_numpy()}
            colors = np.zeros((len(values),4), dtype=float)
            colors[:] = (1., .15, .15, .8)
            colors[values == 1] = (.15, 1., .3, .8)
            layer.face_color = colors
            layer.size = self.point_size.value()
            template = "{label_id}: {type}" if self.show_ids.isChecked() else "{type}"
            layer.text = {"string": template, "color": "white", "size": self.text_size.value(), "anchor": "center"}
            choice = self.filter_combo.currentIndex()
            layer.shown = np.ones(len(values), dtype=bool) if choice == 0 else values == choice-1
            layer.selected_data = set()
            layer.refresh()
            self.update_status()

        def set_type(self, value):
            if self.doc is None or self.points_layer is None:
                return
            indices = set(self.points_layer.selected_data)
            if indices:
                self.doc.set_types(self.current_channel, indices, value)
                self.refresh_points()

        def navigate(self, delta):
            index = max(0,min(len(entries)-1,self.image_combo.currentIndex()+delta))
            self.image_combo.setCurrentIndex(index)

    editor = Editor()
    class CloseGuard(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Close and editor.doc is not None and editor.doc.dirty:
                answer = QMessageBox.question(None,"Unsaved marker calls","Save the current draft before closing?",
                                              QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
                if answer == QMessageBox.Cancel or (answer == QMessageBox.Save and not editor.save(False)):
                    event.ignore()
                    return True
            return False
    close_guard = CloseGuard(viewer.window._qt_window)
    viewer.window._qt_window.installEventFilter(close_guard)
    # Keep editor objects alive throughout the desktop event loop.
    viewer.window._qt_window._myoclass_editor = editor
    viewer.window._qt_window._myoclass_close_guard = close_guard
    napari.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="MyoClass review_session.json produced by the notebook")
    parser.add_argument("--image-id", help="Image to select when opening the batch")
    parser.add_argument("--validate-session", action="store_true", help="Validate review tables without opening napari")
    args = parser.parse_args()
    if args.validate_session:
        if not args.session:
            parser.error("--validate-session requires --session")
        payload=json.loads(Path(args.session).read_text(encoding="utf-8"))
        for entry in payload["entries"]:
            ReviewDocument(entry)
        print(f"Validated {len(payload['entries'])} review table(s).")
    else:
        launch_editor(args.session, args.image_id)
