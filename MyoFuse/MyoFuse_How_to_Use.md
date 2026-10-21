# MyoFuse: How to Use (v1.1.0)

MyoFuse measures the fusion index (FI) in two-channel fluorescence images of myotube cultures. It uses Cellpose to segment nuclei and the Svetlana classifier to identify nuclei inside myotubes. The Linux and Windows notebooks implement the same workflow; use the notebook supplied for your operating system. See the [MyoTools README](../README.md) for installation and the [MyoFuse project README](README.md) for the publication and citation.

## 1. Install, launch and obtain models

Download and extract the [complete ZIP for your operating system](../Downloads/README.md), run `INSTALL.bat` (Windows) or `bash INSTALL.sh` (Linux), and open the MyoTools desktop shortcut. Choose **MyoFuse** in the Hub. For manual startup, activate `myofuse_env`, start from the MyoTools root, and run the appropriate command:

```bash
voila MyoFuse/Codes/linux/MyoFuse_linux_v1.1.0.ipynb
```

On Windows, use `voila MyoFuse/Codes/windows/MyoFuse_win_v1.1.0.ipynb` instead. Leave the Voilà terminal running during analysis.

Before opening MyoFuse, select **Models** in the Hub and download **MyoNuclei**. The Hub verifies the release file's size and SHA-256 and saves it at `Hub/runtime/models/MyoNuclei`; the notebook then proposes this path. The installer fetches the separate **Svetlana** classifier at `MyoFuse/Models/Svetlana/MyoFuse.pth`. Its `Config.json` must stay in the same folder. Both file selectors let you choose another model if needed. If you download a model while the notebook is already open, reopen the application to see its new default path.

The models are downloaded separately from the Windows/Linux ZIPs and are kept when the environment uninstaller runs. They remain inside the extracted MyoTools installation, so keep that folder if you intend to reuse them. A verified download establishes file identity; check model suitability on representative images before processing a cohort.

## 2. Choose images and stages

In **Choose files**, select a local image folder (initially your Desktop) and check the proposed model paths. Original two-channel `.tif`, `.tiff` and `.czi` images can be split into myotube and nuclear channels. Set **Myotube channel** and **Nuclei channel** using indices starting at **0**. The defaults are `0` and `1`.

The stage checkboxes allow you to reuse prepared data:

| Setting | When enabled | When disabled |
| --- | --- | --- |
| **Split original channels** | Reads original images and writes the myotube and nuclear images to `Images/` and `Nuclei/`. | Uses existing matching images in `Images/` and `Nuclei/`. |
| **Run nuclei segmentation** | Uses `MyoNuclei` to make labeled masks in `Masks/`. | Uses existing labeled masks in `Masks/`. |
| **Run classification and quantify FI** | Uses Svetlana and its adjacent `Config.json` to produce classifications and FI. | Stops after the enabled preparation/segmentation stages. |

Check that prepared files correspond to the same images and geometry when skipping a stage. Select a valid model file when its stage is enabled.

## 3. Adjust parameters and preview a crop

**Cellpose diameter** defaults to `24` pixels. Segmentation and classification devices each offer **GPU** and **CPU**; both default to GPU in the interface, so select CPU if the computer cannot use the requested GPU. Classification also exposes **Upper percentile** (`99.7`), **Half patch size** (`100`) and **Batch size** (`512`). The patch size should match the classifier training setup. The **Outputs** section controls annotated prediction images, normalized images and preview downsampling.

Use **Show diameter guide** to inspect the diameter on a representative nuclear crop. **Test segmentation + classification on crop** previews the nuclear signal, Cellpose mask and classifier calls; its FI describes only that crop and **does not write batch outputs**. Confirm channel assignments, mask quality and inside/outside calls before analyzing the entire field. A preview cannot establish that all images in a batch are suitable.

## 4. Run, resume and inspect results

- **Launch new analysis** starts fresh and backs up a previous `Fusion_index.xlsx` in `Log/` before resetting checkpoints.
- **Resume analysis** checks stored per-image signatures and outputs, reuses completed stages when inputs and settings still match, and processes missing or changed work.

The selected image folder contains `Images/`, `Nuclei/`, `Masks/`, optional `Predictions/` and `Normalized_images/`, and `Log/` with checkpoints, image-level results and backups. The final `Fusion_index.xlsx` is written **in the selected image folder**. Its rows report detected nuclei, counts classified inside and outside myotubes, FI (%) and status. Images with no detected nuclei have no numeric FI; failures and skipped images require review in the Voilà status/log output. Do not interpret a partial workbook as a complete batch.

When resuming, retain the intermediate folders and `Log/`. If a source image, a model or relevant parameters have changed, inspect the resulting stage outputs and FI again. The model files and scientific image folders are retained by the MyoTools environment uninstaller; deleting the entire extracted installation folder is a separate action that would also remove locally stored models.
