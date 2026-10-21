# MyoSurface: How to Use (v1.0.0)

MyoSurface quantifies the fraction of an acquired fluorescence image covered by myotubes. It performs background correction, thresholding and area measurement on one full-resolution 2D plane per image. **It does not use a downloadable model.** See the [MyoTools README](../README.md) for installation.

## 1. Launch and choose images

Download and extract the [complete ZIP for your operating system](../Downloads/README.md), install MyoTools, and choose **MyoSurface** from the desktop Hub. To start it manually from the MyoTools root with the shared environment activated:

```bash
conda activate myotools
voila MyoSurface/MyoSurface_v1.0.0.ipynb
```

Keep the Voilà terminal running. Select an image folder in **Input images**; the selector starts on your Desktop. Click the chooser's **Select** button, then **Scan image folder** and choose a representative **Preview image**. The batch reads `.tif`, `.tiff` and `.czi` files **directly in that folder**; it does not recursively traverse subfolders. Input images are not overwritten.

## 2. Select the image plane

**Myotube channel** starts at **1**, following the original Fiji script; it defaults to `1`. **Scene**, **Time** and **Z plane** start at **0** and default to `0`. The **Reconstruct CZI mosaics when supported** option is enabled by default. The notebook reads one selected YX plane per image, not all scenes, times or Z planes in a stack. Verify the scene, dimensions and mosaic coverage on an example image before the batch.

## 3. Tune segmentation on a representative crop

| Parameter | Default | Effect |
| --- | --- | --- |
| **Rolling-ball radius** | `200` px | Scale used for background subtraction. |
| **Zero-pixel replacement** | `3500` | Temporary fill for zero pixels during background correction only. |
| **Threshold (raw units)** | `200` | Threshold applied after correction. |
| **Median radius** | `1` px | Smoothing before area filtering. |
| **Minimum area** | `500` px² | Removes smaller connected regions. |
| **Area connectivity** | 4-connected | Can be changed to 8-connected. |

**Auto-estimate on preview image** suggests a single zero-pixel replacement based on nonzero intensities in the selected image. It is a global approximation, not a user-drawn background-only region. **Prepare interactive crop** displays the corrected crop, thresholded mask and overlay. Move the crop center or change its size to inspect representative regions. **Suggest Otsu threshold** is a suggestion on that crop; adjust the slider and use **Apply threshold** to transfer the chosen value into the batch threshold setting. The crop is for tuning only: the batch processes full images without application-level tiling. Parameters are held constant across images in the batch.

The reported coverage uses pixels acquired in the **original** image:

`Area percent (%) = 100 × foreground pixels within (original intensity > 0) / pixels with original intensity > 0`

Pixels that were exactly zero in the original image are excluded from both numerator and denominator, even if they were temporarily filled for background correction. If there are no acquired pixels, coverage is undefined and the file is reported as an error. Compare masks with your Fiji/reference workflow on representative images before scientific use; numerical agreement of the background correction has not been established for every acquisition.

## 4. Export and resume

**Save binary masks (0 / 255 TIFF)** is enabled by default; **Save background-corrected images** is optional. **Launch new analysis** reprocesses the images and backs up an earlier results CSV in `Log/`. **Resume analysis** skips unchanged images whose matching outputs and checkpoints still exist, and recomputes changed or incomplete images.

The output is always created within the selected input folder:

```text
<image folder>/MyoSurface_Output/
├── MyoSurface_results.csv
├── Masks/          # Optional 0/255 TIFF masks
├── Corrected/      # Optional background-corrected TIFFs
└── Log/            # Checkpoint, analysis manifest, per-image parameters and backups
```

The CSV has one row per current input file, including a status or error for unsuccessful images. It records coverage percentage, foreground and valid pixel counts, excluded zero pixels, dimensions and the selected parameters. Review the masks and the **Status**/**Error** columns rather than relying only on the final progress count. Keep `Log/` and requested image outputs if you intend to resume; changing an image or parameters can trigger reprocessing.
