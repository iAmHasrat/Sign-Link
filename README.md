# Sign-Link (Skeletal-Based Sign Language Translation)

Welcome to **Sign-Link**, a skeletal-based translation pipeline adapted from the SOTA Two-Stream Sign Language Translation architecture for **Indian Sign Language (ISL)** using the **iSign Poses Dataset v1.1**.

This branch (`slrt-sentence-level`) represents our last iteration of sentence-level translation training, implementing key structural improvements to visual-text mapping, training speed, and checkpoint recovery.

---

## 🚀 Key Improvements in this Iteration

### 1. Upgraded Residual VLMapper (Gradient Bridge)
* **Problem**: The original codebase used a simple 2-layer Feed-Forward network to project 512-dimensional keypoint features to the 1024-dimensional mBART text space. Gradients backpropagating from the massive 600M parameter translation network were vanishing, causing *representation collapse* (the language model ignored the poses and hallucinated generic text).
* **Solution**: We replaced the MLP with a **Residual Block Projection Architecture**. A projection layer maps the 512 visual features to 1024 dimensions, followed by two **Residual Blocks with skip connections**. This keeps the gradient flow strong and forces the model to align visual movements directly to mBART text spaces.

### 2. Validation Speed Optimization (2x Speedup)
* **Problem**: Validation was taking over **20 minutes per epoch** (running every 2,000 steps with 3-beam search decoding on 12,684 validation samples).
* **Solution**:
  1. Set validation frequency `freq` to `6000` steps (evaluating once per epoch).
  2. Changed validation decoding to **Greedy Decoding (`num_beams: 1`)** during training.
  * **Result**: Wall-clock training time per epoch dropped from **41 minutes down to 23 minutes** (an almost 2x speedup!) with zero degradation of final model performance (final testing still uses the full `num_beams: 5`).

### 3. Non-Strict Checkpoint Loading & Optimizer Recovery
* Added a custom parameter-matching check in `training.py` that maps learning rates to DDP submodules (`recognition_network`, `vl_mapper`, `translation_network`).
* Implemented `strict=False` state loading and a custom **Optimizer State Filter** that cleans out mismatched state history when changing projection architectures, allowing seamless recovery/resume from checkpoints.

### 4. Smart Storage Management
* Patched the checkpoint saver to **delete the previous checkpoint before saving the new one** and **symlink `best.ckpt`** instead of copying it. This cut the concurrent storage requirements of 7.1 GB checkpoints from 21.3 GB down to **only 7.1 GB**, preventing network-mount out-of-disk crashes.

---

## 📊 Dataset: iSign Poses v1.1
This project utilizes the Indian Sign Language **iSign dataset** (101,477 training samples, 12,684 validation samples).
* **Gloss-Free Training (`S2T_glsfree`)**: Because the iSign dataset does not contain word-for-word gloss labels, the CTC loss contribution is zeroed out (`recognition_weight: 0`). The model translates raw skeletal keypoints (576 coordinates per frame) directly to English sentences.
* **Coordinate Normalization**: Includes hips-origin centering, wrist-relative hand scaling, and shoulder-to-shoulder width normalization inside `ISignDataset.py` to ensure rotation/translation-invariant skeletal inputs.

---

## 🛠️ Usage

### Prerequisites
Activate the environment and verify GPU configuration:
```bash
conda env create -f environment.yml
conda activate slt
```

### Configuration
The config file `experiments/configs/TwoStream/isign_s2t.yaml` controls all parameters. Notable defaults:
* `total_epoch`: 40
* `batch_size`: 16
* `learning_rate`:
  * `default` / `mapper`: `1.0e-04`
  * `translation` (mBART): `1.0e-05`

### Training
To resume training from the latest checkpoint on Port 29555:
```bash
torchrun --nproc_per_node=1 --master_port=29555 training.py --config experiments/configs/TwoStream/isign_s2t.yaml
```

### Monitoring Dashboard
We provide a custom interactive terminal dashboard to monitor evaluation metrics and loss values in real-time. Run it in a separate terminal window:
```bash
python3 monitor.py
```

---

## 📖 References & Citations

If you build upon this work, please reference the original dataset and baseline models:

* **iSign Dataset**: [iSign: A Large-Scale Indian Sign Language Dataset for Translation](https://github.com/Tarandeep98/slrt)
* **Two-Stream Base Code**:
  ```bibtex
  @article{chen2022two,
    title={Two-Stream Network for Sign Language Recognition and Translation},
    author={Chen, Yutong and Zuo, Ronglai and Wei, Fangyun and Wu, Yu and Liu, Shujie and Mak, Brian},
    journal={NeurIPS},
    year={2022}
  }

  @InProceedings{Chen_2022_CVPR,
    author    = {Chen, Yutong and Wei, Fangyun ...},
    title     = {A Simple Multi-Modality Transfer Learning Baseline for Sign Language Translation},
    booktitle = {CVPR},
    year      = {2022}
  }
  ```
