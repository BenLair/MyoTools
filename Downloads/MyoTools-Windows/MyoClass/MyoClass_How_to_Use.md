# MyoClass: How to Use (v1.0.1, Cellpose 3)

MyoClass assigns **independent binary fluorescence marker calls** to pre-segmented muscle fibers. It can segment marker-positive regions using Cellpose 3, collect manual classifications in Napari, infer one complementary negative category, and export fiber counts, CSA, minimum Feret diameter, and combinations of markers.

**MyoClass does not create the reference fiber segmentation.** First provide 2D labeled fiber masks from MyoSeg or another validated segmentation workflow. See the [MyoTools README and installation guide](../README.md) and the [MyoSeg usage guide](../MyoSeg/MyoSeg_How_to_Use.md).

## 1. Launch MyoClass

```bash
conda activate myotools
voila MyoClass/MyoClass_v1.0.1.ipynb
```

Run from the **MyoTools repository root**. Voilà provides the browser interface; **Napari opens separately on the computer running Voilà**.
After extracting and installing the Windows or Linux distribution, you can instead open the MyoTools desktop shortcut and select **MyoClass** on its landing page. The fluorescence image folder chooser starts on your **Desktop**.

## 2. Prepare image and mask folders

In **Choose files**, select:

1. **Fluorescence image folder:** original multichannel `.tif`, `.tiff`, OME-TIFF, or `.czi` images.
2. **Reference fiber masks:** 2D integer-labeled TIFFs corresponding to those images. Select MyoSeg's `MyoSeg_results/Masks/` or your own validated masks.
3. **Cellpose 3 typing model:** open **Models** in the MyoTools hub to download and verify the `MyoClass` release asset. Its path under `Hub/runtime/models/` is then proposed in the model chooser when you next open MyoClass. You can select another custom model trained to segment **fluorescence-positive signal regions**. A model is required only if any enabled marker uses **Automatic** mode; fully Manual/Inferred projects do not need the download.
4. **Output / existing project folder:** leave blank for `<fluorescence image folder>/MyoClass_results/`, or choose an existing MyoClass project to resume work.

**Mask convention:** background `0`, a distinct positive integer label for each fiber, and matching field of view. Reference fiber IDs are kept fixed throughout classification and review.

Use **Check image/mask pairs** before analysis. MyoClass recognizes matching image/mask stems (including common `_masks` and `_cp_masks` suffixes) and can associate masks exported by MyoSeg. For multiscene images, ensure that each scene has an unambiguous corresponding mask. Files with ambiguous or missing partners are reported instead of silently paired.

Enable **Include subfolders** when needed. Channel indices, time points, and Z-plane indices are **0-based**. **Process all CZI scenes / TIFF series** is enabled by default; each selected scene and plane is analyzed in 2D.

## 3. Define markers: Automatic, Manual, or Inferred

For each marker row, choose **Use**, the original image **Channel** index, a readable **Marker / type** name, and one of the following modes:

| Mode | How calls are obtained | What must be supplied |
| --- | --- | --- |
| **Automatic (Cellpose)** | Cellpose 3 segments fluorescence signal in that channel; each fiber is called positive based on signal overlap. Calls remain editable in Napari. | Fluorescence channel + custom Cellpose 3 typing model. |
| **Manual (Napari)** | All fiber calls start at `0` (negative), then the user assigns positives/negatives in Napari. The channel is shown for visual review but is **not** sent to Cellpose. | Fluorescence channel; no Cellpose typing model needed for this channel. |
| **Inferred from other negatives** | A fiber is positive **only when all other enabled Automatic/Manual markers are negative**. This category is recalculated after edits and at export. | At least one other enabled source marker; no dedicated fluorescence channel or model. |

**Only one marker can be Inferred**, and it can be at any channel index, not necessarily the last row. You can add more marker rows with **Add marker channel**. Enabled physical channel indices must be unique.

The three initial example rows are **channel 0 = Manual**, **channel 1 = Automatic**, and **channel 2 = Inferred**. Adapt all three to your own acquisition rather than assuming they match your staining.

### Example: two measured markers and one inferred class

| Channel | Example name | Mode | Result |
| --- | --- | --- | --- |
| `ch0` | Marker A | Manual | Assign fiber calls in Napari. |
| `ch1` | Marker B | Automatic | Cellpose predicts signal; correct calls in Napari if needed. |
| `ch2` | Other / neither | Inferred | Positive only if both `ch0 = 0` and `ch1 = 0`. |

Automatic and Manual markers are **independent**, not mutually exclusive: a fiber can be `ch0 = 1` and `ch1 = 1`. Such double-positive fibers are preserved as combinations/hybrids, not forced into a single category. The Inferred category is read-only in Napari because it is derived from the other markers.

## 4. Prepare the fluorescence channels

| Setting | Meaning |
| --- | --- |
| **TIFF channel layout** | Auto from TIFF/OME axes; or explicitly channel-first (`C x Y x X`) / channel-last (`Y x X x C`) for ambiguous 3D TIFFs. |
| **Time point / Z plane** | Select the 2D plane to classify (both default `0`). |
| **Resize fluorescence images to the reference mask dimensions** | Allow resizing when image and mask have different pixel dimensions but show **the same field of view**; off by default. |
| **Background handling** | `Subtract outside reference fibers` (default), `Set outside fibers to zero`, or `No background masking`. |
| **Use reference label edges as support before inversion** | In subtraction mode, derive suppression from fiber-label edges rather than whole fiber regions; off by default. |
| **Subtraction amplitude** | Use the 99th intensity percentile across measured channels (default) or a fixed intensity. |
| **Subtraction strength / Fixed intensity / Mask smoothing** | Configure background suppression and optional Gaussian smoothing (default strength `1`, fixed intensity `2000`, smoothing `0`). |
| **Normalize positive intensities** | Rescale positive values while preserving zero background; enabled by default. |

**Resizing is not image registration.** Do not use this switch to compensate for different crops, translations, or mismatched fields of view. Click **Preview prepared input** and inspect fluorescence relative to reference fiber boundaries before typing.

For masks exported from resized MyoSeg images, resizing the original fluorescence to the mask dimensions may be necessary. The final measurement calibration is taken from the **reference mask**, not from the original fluorescence pixel size.

## 5. Run automatic/manual typing

Only **Automatic** markers run through Cellpose. All **Manual** source channels are prepared for Napari, while **Inferred** channels do not need an image plane.

| Setting | Default | Meaning |
| --- | --- | --- |
| **Fiber diameter (px)** | `70` | Typical signal-object diameter supplied to Cellpose. |
| **Processing device** | `Auto` | CUDA GPU when available, otherwise CPU. |
| **Flow threshold / Cell probability threshold** | `0.4` / `0` | Cellpose mask filtering. |
| **Minimum object size (px^2)** | `15` | Reject smaller Cellpose signal objects. |
| **Cellpose batch size** | `8` | Reduce when GPU memory is limited. |
| **Use Cellpose percentile normalization** | Enabled | Cellpose's internal normalization. |
| **Positive overlap fraction** | `0.5` | Positive if **one** Cellpose-predicted signal object overlaps at least 50% of the reference fiber area. |

**Overlap is not a probability.** For each reference fiber and automatic marker, MyoClass takes the *largest overlap with one predicted signal object* and divides it by reference fiber area. It does **not** add the overlaps of separate signal fragments.

Recommended order:

1. Click **Check image/mask pairs** to detect missing or ambiguous reference masks.
2. Click **Preview prepared input** to check marker channel selection and alignment.
3. Click **Test first image**; inspect the generated signal masks and automatic calls.
4. Click **Run / resume typing** for all matching images. Use **Stop after image** if you need to interrupt safely.

Per-image predictions, mappings, and project state are stored for reuse. **Recompute automatic outputs** bypasses matching checkpoints. The notebook tries to preserve existing review workbooks, but changes to segmentation, models, or source images may make old reviews stale or require resetting them; verify review status before export.

## 6. Review classifications in Napari

After typing, use section **Review marker calls in Napari**:

1. Select the image in the dropdown (its status shows **Draft**, **Reviewed**, or a problem state).
2. Leave **Napari Python (optional)** empty when using the shared Conda environment.
3. Click **Open Napari review**. A **separate desktop window** opens locally on the machine running Voilà.
4. Select the **Marker to view / edit**. Choose one or more fiber centroid points in the Napari **Points** layer (selection mode).
5. Assign **F1 = negative (0)** or **F2 = positive (1)** using the keyboard or the panel buttons. This changes only the chosen marker call(s), not the mask or centroid coordinates.
6. Repeat for every Automatic/Manual marker. A Manual channel starts fully negative: **you must inspect and assign positives where appropriate**.
7. Click **Save draft (Ctrl+S)** to save progress; once all source markers have been checked, click **Mark image reviewed**.
8. Close Napari, then click **Refresh review status** in MyoClass before exporting.

Useful Napari controls include **Previous / Next** image, **Show all fluorescence channels**, **Visible points: All / Negative / Positive**, **Show fiber label IDs**, **Point size**, and **Text size**. Positive points appear green and negative points red. If you select the **Inferred** category, its values update after source-marker edits and **cannot be directly changed**.

**Save draft is not final approval.** An image is eligible for the default **Reviewed images only** export only after **Mark image reviewed** was clicked. If you change calls later, mark the image reviewed again. On unsaved changes, navigation saves a draft; closing Napari prompts about saving.

### Review files, resetting, and standalone launch

`Automatic/` holds original predictions and `Review/` holds editable review workbooks and status metadata. **Reset selected review** replaces the chosen draft with the automatic calls and backs up its previous review files in `Review/Backups/`. Use this deliberately: unsaved/previous manual calls will no longer be the active review.

MyoClass creates its current Napari correction script at:

```text
<project output>/Log/Tools/Corrections_napari_MyoClass.py
```

The script is generated when **Open Napari review** is launched. If needed after its first generation, it can also be started from a terminal using its generated session file:

```bash
python "<project output>/Log/Tools/Corrections_napari_MyoClass.py" --session "<project output>/review_session.json"
```

Use the script **generated by this notebook version**. Older standalone copies may not implement the newer per-marker Manual/Automatic/Inferred behavior correctly. Do not edit review Excel workbooks externally while Napari is open; the reviewer checks file integrity and can reject conflicting changes.

## 7. Export fiber measurements

Select the **Classification source** in section **Export results**:

| Source | What is exported |
| --- | --- |
| **Reviewed images only** (default) | Only images marked **Reviewed** in Napari, including manual and corrected automatic calls. |
| **Initial calls (manual markers = 0)** | The initial, uncorrected automatic calls. Every Manual marker remains negative; the Inferred category is recomputed accordingly. Useful for comparison/quality control. |

Set the **Mask pixel calibration** to reference-mask metadata (default, with manual fallback) or to an explicit **Mask pixel size**. Configure minimum Feret calculation, exclusion of border-touching fibers, min/max CSA, and CSA/Feret histogram bins. Changing these **measurement-only** settings does not rerun automatic typing.

Click **Export fiber measurements** after closing Napari. An export based on Reviewed classifications **will not include Draft images**. If none are eligible, the export raises an error; confirm the **Reviewed** status or choose **Initial calls** for preliminary results.

The export reports **all included fibers**, a positive-fiber subset for **each marker**, and **marker combinations**. A hybrid fiber may appear in more than one marker-specific summary. Marker percentages use the number of included fibers in that image as the denominator. Excluded fibers remain in the detailed table with their exclusion reasons.

## 8. Inspect outputs and resume projects

```text
<fluorescence image folder>/
└── MyoClass_results/
    ├── Reference_masks/         # Copied, fixed integer-labeled fiber masks
    ├── Prepared_channels/       # Prepared TIFF for each Automatic/Manual source channel
    ├── Signal_masks/            # Cellpose signal masks for Automatic channels only
    ├── Automatic/               # Initial per-fiber mapping workbooks
    ├── Review/                  # Editable mappings and review status JSON
    │   └── Backups/            # Previous copies after reset/edit
    ├── Previews/                # Selected prepared-image and fiber-boundary previews
    ├── Exports/
    │   ├── automatic/
    │   └── reviewed/
    ├── Log/                     # Project, settings, errors, Napari logs, backups, tools
    └── review_session.json      # Session opened by the Napari reviewer
```

Both `Exports/automatic/` and `Exports/reviewed/` contain `segmentation_results_by_type.xlsx` when exported using that source, plus:

- `Detailed_Labels_all.csv`
- `Summary_all.csv`
- `Combinations.csv`
- `Export_issues.csv`

The Excel workbook includes detailed fiber rows, `Summary_all`, per-marker `Summary_chN`, CSA/Feret count and percentage distributions for all fibers and each marker, `Combinations`, `Marker_names` (including mode/origin), `Export_issues`, and `Parameters`. The detailed table includes individual 0/1 marker calls, combinations, inclusion status, and classification source.

To resume work, set **Output / existing project folder** to the original `MyoClass_results/` and click **Load existing project**. Saved image/mask/model paths and marker settings are restored where those paths still exist. Then use **Refresh review status**, **Open Napari review**, or **Export fiber measurements** as appropriate. Keep the `Log/` and `Review/` folders if you move or archive a project.

## 9. Troubleshooting

| Symptom | Likely cause / action |
| --- | --- |
| No image/mask pairs | Check TIFF/CZI scenes, mask suffixes, directory selection, and MyoSeg output pairing; run **Check image/mask pairs**. |
| Image and mask shapes differ | Confirm the same field of view; enable resizing only for a genuine resolution difference, not misregistration. |
| Cellpose loads on CPU | Auto mode falls back when PyTorch cannot access NVIDIA CUDA; CPU is supported. |
| Napari window does not appear | Napari opens on the Voilà **host computer**. Check the terminal/Napari log and Qt desktop support. The shared `myotools` environment uses **PySide6**; avoid installing PyQt6 alongside it. |
| Review shows **Draft** | Click **Mark image reviewed** in Napari, save, close, and refresh status. |
| Review shows **Stale** or an integrity warning | Check whether automatic inputs/settings changed or review files were modified outside Napari. Back up work and use **Reset selected review** only when appropriate. |
| Reviewed export produces no workbook | Confirm that at least one valid image is marked **Reviewed**; inspect review status and `Export_issues` for skips. |
| An inferred call seems wrong | Inspect all source-marker calls: the inferred marker is `1` only when **every other enabled source marker is `0`**. |

