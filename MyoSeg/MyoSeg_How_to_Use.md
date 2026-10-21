# MyoSeg: How to Use (v1.1.1, Cellpose 3)

This guide describes `MyoSeg_v1.1.1.ipynb`, a Voilà interface for **2D skeletal muscle fiber segmentation and morphometry in fluorescence or RGB H&E images**. MyoSeg uses a custom Cellpose 3 model appropriate to the staining and calculates fiber cross-sectional area (CSA), optional minimum Feret diameter, and size distributions.

The approved v1.1.1 notebook supports RGB H&E preparation, configurable two-channel or three-channel Cellpose input, and color previews.

For software installation, see the [MyoTools README and installation guide](../README.md). After extracting the Windows or Linux distribution and running its installer, the simplest way to launch MyoSeg is the MyoTools desktop shortcut. Choose **MyoSeg** on the Hub landing page.

## 1. Launch MyoSeg

From the **MyoTools repository root**, after installing the shared environment:

```bash
conda activate myotools
voila MyoSeg/MyoSeg_v1.1.1.ipynb
```

Keep the Voilà terminal running while using the browser interface; press `Ctrl+C` in the terminal when finished. The image folder chooser opens on your **Desktop**; select your image folder there or navigate to another one.

Open **Models** in the MyoTools hub to download and verify the weights from [MyoTools Releases](https://github.com/BenLair/MyoTools/releases):

| Model asset | Image type | Availability |
| --- | --- | --- |
| [`MyoSeg`](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg) | Fluorescence / single-channel | Existing release asset. |
| [`MyoSeg_HE`](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg_HE) | H&E brightfield / original RGB | Available as the `MyoSeg_HE` release asset. |

The model chooser proposes `MyoSeg` for fluorescence and `MyoSeg_HE` when you switch **Image type** to H&E, if those files were installed by the hub **before opening MyoSeg**. Reopen the application after a new download. You can still select a custom file with the chooser's **Select** button; each image mode remembers its own chooser. The model filename does not set Cellpose's input channel configuration. The MyoClass model is for fluorescence marker assignment and is not the fiber segmentation model. The verified release files live under `Hub/runtime/models/` inside this MyoTools installation, outside the distributed ZIP contents.

## 2. Prepare the image folder

Put source `.tif`, `.tiff`, `.ome.tif`, or `.czi` files in an input folder. Enable **Include subfolders** to process nested directories. Image and file selection is local to the computer running Voilà.

- **Fluorescence channel, time-point, and Z-plane indices start at 0.** The default fluorescence channel is `3`; change it to match your acquisition. It is ignored in H&E RGB mode.
- **Process all CZI scenes / TIFF series** is enabled by default. Each selected scene becomes a separate 2D analysis. Disable it to use only the first scene/series.
- The selected **Time point** and **Z plane** apply to each scene; MyoSeg does not segment an entire 3D Z stack.
- For TIFF files with ambiguous 3D layouts, choose **Channels first: C x Y x X** or **Channels last: Y x X x C**. Leave **Auto** for correctly annotated OME images.
- A single-channel image uses its only channel even when a higher channel index is requested.

For H&E, use an image containing the original red, green and blue components. In RGB mode, TIFF input must expose one sample/channel axis with at least three components; the first three are used as RGB (an additional alpha component is ignored). Do not treat arbitrary fluorescence channels as RGB. For RGB CZI input, the current reader path requires the colors to be exposed as at least three **C channels**, and takes the first three in RGB order. If the reader exposes your brightfield acquisition differently, export an RGB TIFF from the acquisition software.

**Scenes, planes and mosaics:** the all-scenes option processes each scene/series exposed by the reader at the selected T/Z position. It does not iterate over all time points, Z planes or pyramid resolution levels. MyoSeg sends each complete prepared 2D scene to Cellpose in one call; this version adds no separate application-level tiling workflow. Inspect the preview and reported dimensions to confirm which field of view your CZI reader returned.

By default, outputs are written to `<input folder>/MyoSeg_results/`. You may enter another **Output folder**. Source images are not overwritten.

## 3. Choose a workflow

| Workflow | Input | What MyoSeg does |
| --- | --- | --- |
| **Full pipeline: prepare -> segment -> measure** | Fluorescence or RGB H&E images + appropriate custom Cellpose 3 model | Reads, optionally resizes, prepares the selected image type, segments fibers, and exports measurements. |
| **Prepare images only** | Fluorescence or RGB H&E images | Saves prepared grayscale or RGB 2D image planes; no segmentation model or measurements required. |
| **Measure existing label masks** | 2D integer-labeled TIFF masks | Measures existing masks without re-segmenting or resizing them; no segmentation model required. |

For existing masks, **background must be 0 and each fiber must have a unique positive integer label**. The input folder should contain the mask TIFFs to measure. If you have manually corrected a mask, this mode lets you recompute morphometry without running Cellpose again.

## 4. Set image preparation parameters

| Setting | Description |
| --- | --- |
| **Image type** | **Fluorescence / single-channel (original workflow)** (default) or **H&E brightfield / original RGB image**. |
| **Fluorescence channel index** | Index of the fiber-staining channel in the original multichannel image (default `3`). Disabled and ignored in RGB mode. |
| **TIFF channel layout** | Automatically read TIFF/OME axes or manually specify a 3D channel-first/last layout. |
| **Process all CZI scenes / TIFF series** | Analyze every scene/series or only the first. |
| **Time point / Z plane** | Select one 2D plane from each scene (defaults `0` and `0`). |
| **Resize factor** | Spatial image resize before segmentation (default `1`, no resizing). Cellpose diameter is defined on this resized image. |
| **Pixel calibration** | Use manual pixel size or image metadata with manual fallback. |
| **Input pixel size (um)** | Manual input calibration (default `0.6928 um/pixel`; replace with your actual acquisition value). |
| **Normalize positive intensities. Keep zero background** | Rescale positive fluorescence intensities while preserving zero background (enabled by default). Disabled and ignored in RGB mode. |

**RGB preparation:** with resize factor `1`, RGB pixel values are kept unchanged. Resizing changes the spatial sampling while retaining three color components; MyoSeg does not apply the fluorescence normalization separately to R/G/B. Prepared RGB images are saved as RGB OME-TIFFs. This does not disable Cellpose's own optional percentile normalization during segmentation.

**Calibration matters:** CSA is reported in square micrometers and minimum Feret diameter in micrometers. When resizing images, the effective X/Y pixel size is adjusted automatically. If measuring existing masks, supply the **mask's current pixel size**; masks are not resized.

## 5. Set Cellpose segmentation parameters

| Setting | Default | Description |
| --- | --- | --- |
| **Cellpose 3 model** | Downloaded `MyoSeg` or `MyoSeg_HE` if available; otherwise user-selected | Model trained to identify muscle fiber regions. Required for the full pipeline. |
| **Fiber diameter (px)** | `80` | Expected fiber diameter in the **prepared/resized** image. |
| **Processing device** | `Auto` | Use CUDA if PyTorch detects a compatible GPU, otherwise CPU; CPU and required CUDA can also be selected manually. |
| **RGB model input** | Two selected channels | RGB mode only: use the standard two-channel input or all three RGB channels, according to model training. |
| **RGB Cellpose channel 1** | Grayscale (`0`) | First input for a standard two-channel model. Choices: grayscale, red (`1`), green (`2`), blue (`3`). |
| **RGB Cellpose channel 2** | None (`0`) | Second input for a standard two-channel model. Choices: zero channel, red (`1`), green (`2`), blue (`3`). |
| **Flow threshold** | `0.4` | Cellpose mask consistency filter. |
| **Cell probability threshold** | `0` | Cellpose foreground/cell probability threshold. |
| **Minimum size (pixels)** | `15` | Minimum segmented object area in prepared-image pixels (px²). |
| **Cellpose batch size** | `8` | Reduce if GPU memory is insufficient. |
| **Use Cellpose percentile normalization** | Enabled | Apply Cellpose's own intensity normalization in either image mode. Match the setting used for training/inference. |
| **Invert intensities before segmentation** | Disabled | Use only if required by the model/staining. |

Check the segmentation of a representative image before running the whole batch. Changing image preparation or Cellpose settings can change the segmentation and thus downstream measurements.

### RGB source images and model input channels

Keeping the source image in RGB does not mean that the model was trained with three input channels. Match **RGB model input** and the selected colors to the training configuration:

| Training configuration | RGB model input | Channel 1 / channel 2 | Input sent to Cellpose |
| --- | --- | --- | --- |
| Standard Cellpose 3, grayscale | Standard Cellpose 3: two selected channels | Grayscale (`0`) / None (`0`) | `[0, 0]`: RGB combined to grayscale plus a zero second channel. |
| Standard Cellpose 3, selected colors | Standard Cellpose 3: two selected channels | For example Red (`1`) / Blue (`3`), only if used in training | `[1, 3]` in this example. |
| Custom model explicitly trained on all R/G/B components | Custom model trained with all three RGB channels | Selectors disabled | Three-channel model (`nchan=3`), all RGB components passed together. |

The Cellpose color codes in this table differ from the **0-based fluorescence channel index**. In the two-channel RGB mode, grayscale as channel 1 requires **None** as channel 2. Fluorescence mode always uses its selected 2D image with Cellpose channels `[0, 0]`.

For `MyoSeg_HE`, use the channel configuration used to train the model. Do not choose three-channel input solely because the acquisition is an RGB image. Keep resize factor, fiber diameter, normalization and inversion consistent with a validated inference setup.

### First H&E analysis

1. Choose **Full pipeline**, your H&E image folder, a dedicated output folder, and the [`MyoSeg_HE`](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg_HE) model.
2. Set **Image type** to **H&E brightfield / original RGB image**. Confirm TIFF axes if necessary and enter the actual pixel calibration.
3. Choose the model input channel configuration described with the model. Start with resize factor `1` unless your validated setup uses another factor, and adjust diameter in the prepared image's pixels.
4. Click **Preview input**, then **Test first image**. Inspect the full-resolution saved mask and RGB boundary preview before running the dataset.

If GPU memory is insufficient, try a smaller Cellpose batch size or CPU. Any change in resize factor also requires rechecking diameter and segmentation quality.

## 6. Configure fiber measurements

The following options affect **statistics, not the saved label masks**:

| Setting | Behavior |
| --- | --- |
| **Calculate minimum Feret diameter** | Measures the minimum width of each fiber's convex hull of pixel centers. Enabled by default. |
| **Exclude fibers touching the image border** | Exclude border-touching fibers from statistics when enabled. Disabled by default. |
| **Minimum CSA / Maximum CSA** | Exclude regions outside the chosen CSA range. Maximum `0` disables the upper bound. |
| **CSA distribution max / bin width** | Default `6750 um^2` maximum and `250 um^2` bins. |
| **Feret distribution max / bin width** | Default `100 um` maximum and `5 um` bins. |

Distributions include an overflow bin for values at or above the specified maximum. Percentage distributions refer to fibers **included after filtering**. All detected labels remain in the detailed results, including excluded fibers and their reasons.

## 7. Preview, test, run, and resume

1. Click **Preview input** to verify the selected channel, image orientation, and calibration. This displays a preview without running segmentation.
2. Click **Test first image** to run the selected workflow on one image/scene. This **writes real files and measurements** to the output folder. Inspect the saved mask, not only the downsampled preview.
3. Click **Run / resume analysis** to process the dataset. For the preparation-only workflow, this button reads **Prepare images**.
4. Use **Stop after image** to stop safely after the current image/scene. Completed work and checkpoints remain available.

MyoSeg stores per-image checkpoints in `Log/checkpoints.json`. On a later run, it checks source files, model information, settings, and intermediate outputs, and **reuses valid stages**. Changing only measurement filters can trigger remeasurement without repeating segmentation. Enable **Recompute existing outputs (ignore checkpoints)** to force processing again.

Image type and RGB model/channel settings are included in these checks. Updating from v1.0.0 invalidates the relevant cached stages through the application version; expect recomputation. Use separate output folders for fluorescence and H&E analyses if you want to retain both sets of results.

A one-image test or interrupted run can retain valid measurements from previously completed images in its workbook. Check the run summary and `Tables/Errors.csv` rather than assuming all inputs were processed.

## 8. Inspect the outputs

The default output folder has the following structure:

```text
input_folder/
└── MyoSeg_results/
    ├── Prepared_images/          # Selected grayscale plane or RGB image, OME-TIFF
    ├── Masks/                    # 2D integer label masks (*_masks.tif)
    ├── Previews/                 # Optional reduced-resolution PNG previews
    ├── Tables/
    │   ├── Per_image/           # Detailed CSV results for each image/scene
    │   ├── Summary.csv
    │   ├── CSA_Distribution.csv
    │   ├── CSA_Distribution_%.csv
    │   ├── Feret_Distribution.csv
    │   ├── Feret_Distribution_%.csv
    │   └── Errors.csv
    ├── Log/                      # Checkpoints, settings, logs and workbook backups
    └── segmentation_results.xlsx
```

`segmentation_results.xlsx` contains:

- **Summary:** included/detected/excluded fiber counts, mean/median/min/max CSA, mean minimum Feret diameter, calibration and processing status for each image/scene.
- **CSA_Distribution / Feret_Distribution:** counts by size bin.
- **CSA_Distribution_% / Feret_Distribution_%:** corresponding percentages.
- **Detailed_Labels:** one row per original detected fiber with label ID, individual measurements, border flag, inclusion status and exclusion reason. Large tables may be split across numbered sheets.
- **Run_Parameters:** settings used for the export.

A summary with **No fibers detected** or **All fibers excluded** is not equivalent to a successful measurement of ordinary fibers. Review masks and filters. Per-image errors are recorded in `Tables/Errors.csv` and the run log.

`Prepared_images/` and `Masks/` retain the resolution of the prepared image. **Only PNG previews are downsized** to the selected preview limit.

In H&E mode, previews retain RGB colors and show mask boundaries in cyan; fluorescence previews are grayscale with purple boundaries. Both modes export **2D integer fiber label masks**, not RGB label images. CSA and minimum Feret calculations use the calibrated full-resolution masks.

## 9. Use MyoSeg masks in MyoClass

A typical workflow with fluorescence images is:

1. Segment your muscle cross-section in MyoSeg; inspect the label masks in `MyoSeg_results/Masks/`.
2. Launch MyoClass and select the **original multichannel image folder** as its fluorescence input.
3. Select `MyoSeg_results/Masks/` as the **Reference fiber masks** folder. MyoClass can match MyoSeg mask names and use the adjacent `Log/checkpoints.json` metadata.
4. Verify pairing and alignment in MyoClass. If MyoSeg resized the image, enable MyoClass's **Resize fluorescence images to the reference mask dimensions** only if the image and mask still cover the same field of view.
5. Use the reference mask's calibrated pixel dimensions when exporting MyoClass measurements.

MyoClass does **not** alter the reference fiber label IDs. H&E can be analyzed independently in MyoSeg. Before using H&E-derived masks with separate fluorescence images, establish spatial registration and matching fields of view; resizing alone does not align different acquisitions or serial sections. Consult the [MyoClass usage guide](../MyoClass/MyoClass_How_to_Use.md) for typing and Napari review.

