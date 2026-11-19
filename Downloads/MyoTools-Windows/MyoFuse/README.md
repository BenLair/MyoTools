# MyoFuse

MyoFuse quantifies the fusion index (FI) in two-channel fluorescence images of skeletal muscle cell cultures. It segments nuclei with Cellpose, classifies each detected nucleus as inside or outside a myotube, and reports the percentage classified as inside.

For a step-by-step Windows/Linux workflow, model downloads, parameters, preview, outputs and resuming work, see [MyoFuse: How to Use](MyoFuse_How_to_Use.md).

**Version selected for the current MyoTools distributions: v1.1.3.** The application folder contains this version only, with one Linux notebook and one Windows notebook. Previous versions remain available in Git history. Image reading and inference should still be checked on representative microscopy files and the released models.

## Quick start

1. Download and extract the complete Linux or Windows package from the [MyoTools download page](https://github.com/BenLair/MyoTools#download-and-install). Run its installer, or create the environment from the extracted package root:

   ```bash
   conda env create -f Hub/platforms/linux/environments/myofuse.yml
   conda activate myofuse_env
   ```

   On Windows, use `Hub/platforms/windows/environments/myofuse.yml` instead.

2. Open **Models** in the MyoTools hub to download and verify `MyoNuclei` from the [MyoTools releases](https://github.com/BenLair/MyoTools/releases/tag/MyoNuclei). The same model is also published in the [MyoFuse releases](https://github.com/BenLair/MyoFuse/releases). The installer fetches the classifier `MyoFuse.pth`; keep its `Config.json` beside it in `MyoFuse/Models/Svetlana/`.

3. Launch the notebook with Voilà from the repository root:

   ```bash
   voila MyoFuse/Codes/linux/MyoFuse_linux_v1.1.3.ipynb
   ```

   On Windows, run `voila MyoFuse/Codes/windows/MyoFuse_win_v1.1.3.ipynb`. Select one or more image folders in the browser interface; each folder has an independent results run. The installed model files are proposed by default and can be changed there.

4. Use **Launch new analysis** for a fresh run or **Resume analysis** to continue an interrupted run. Image-level results are exported to `Fusion_index.xlsx` inside each `MyoFuse_results/run_…/` result folder. Resume uses the latest run of each selected input folder; legacy projects resume in place.

The input and result folders used by this version are described below. Earlier release candidates and their notes can be retrieved from Git history.

## Inputs and models

- Original images: two-channel `.tif`, `.tiff`, or `.czi` files, including OME-TIFF. Check the time point, Z plane, channel assignments and first output images before processing a large dataset.
- Prepared images: matching myotube images in `Images/`, nuclear images in `Nuclei/`, and labeled nuclei masks in `Masks/`. You can turn off stages that are already complete.
- Segmentation model: `MyoNuclei`, distributed through the releases.
- Classification model: `Models/Svetlana/MyoFuse.pth`, with `Config.json` beside it.

The classifier training images are available on [Zenodo](https://zenodo.org/records/14731491). Test images are available from the [project releases](https://github.com/BenLair/MyoFuse/releases).

## Results

`Fusion_index.xlsx` contains one row per successfully processed image: total nuclei, nuclei inside and outside myotubes, FI in percent, and a `Status` column. Images with no detected nuclei have a blank FI and `No nuclei detected` status. Failed or skipped images are not reported as completed; review the messages in Voilà and resume after correcting the input.

Each result run also holds intermediate `Images/`, `Nuclei/`, `Masks/`, optional `Predictions/` and `Normalized_images/`, and a `Log/` folder with checkpoints, per-image results, and workbook backups.

## Citation

If you use MyoFuse, please cite: Lair B. *et al.* “MyoFuse is a fully AI-based workflow for automated quantification of skeletal muscle cell fusion in vitro.” *Scientific Reports* **16**, 9387 (2026). [https://doi.org/10.1038/s41598-026-40047-y](https://doi.org/10.1038/s41598-026-40047-y).

## License and contact

MyoFuse is released under the [MIT License](https://github.com/BenLair/MyoTools/blob/main/Downloads/MyoTools-Linux/MyoFuse/LICENSE). For questions, contact lair.b1jamin@gmail.com.
