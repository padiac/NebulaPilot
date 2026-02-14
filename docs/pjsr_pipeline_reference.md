# NebulaPilot PJSR Integration Pipeline Reference

This document provides a technical overview of the automated PixInsight pipeline implemented in NebulaPilot using the PixInsight JavaScript Runtime (PJSR).

## Pipeline Architecture

NebulaPilot generates a dynamic `.js` script for each target, which is then executed via `PixInsight.exe -r=<script_path>`. The pipeline follows a standard 5-step astrophotography pre-processing workflow.

### Output Structure
All results are stored in a `PixInsight/` subfolder within your target directory:
```text
[TargetName]/
└── PixInsight/
    ├── calibrated/    # Output of ImageCalibration
    ├── weighted/      # Output of SubframeSelector
    ├── registered/    # Output of StarAlignment
    ├── normalized/    # Output of LocalNormalization
    └── integrated/    # Final master frames (ImageIntegration)
```

---

## Detailed Process Parameters

NebulaPilot uses the following specific parameters for each process, mimicking a high-quality manual/WBPP workflow.

### 1. ImageCalibration
*   **Process**: `ImageCalibration`
*   **Parameters**:
    *   `targetFrames`: Light frames for the specific filter.
    *   `masterBiasPath`: Master Bias from settings.
    *   `masterBiasEnabled`: `true` (if path provided).
    *   `masterDarkPath`: Master Dark from settings.
    *   `masterDarkEnabled`: `true` (if path provided).
    *   `masterFlatPath`: Channel-specific Flat (e.g., H-filter uses H-flat).
    *   `masterFlatEnabled`: `true` (if path provided).
    *   `calibrate`: `true`
    *   `outputDirectory`: `PixInsight/calibrated`
    *   `outputPrefix`: `[Filter]_`

### 2. SubframeSelector (Weighting)
*   **Process**: `SubframeSelector`
*   **Routine**: `MeasureSubframes`
*   **Parameters**:
    *   `subframes`: All files from `calibrated/`.
    *   `subframeScale`: `1.0`
    *   `sortProperty`: `Weight`
    *   **Weighting Method**: `PSF Signal Weight` (This is the default for `Expression` based on signal-to-noise and PSF metrics).
    *   `outputDirectory`: `PixInsight/weighted`

### 3. StarAlignment (Registration)
*   **Process**: `StarAlignment`
*   **Parameters**:
    *   `referenceImage`: Automatically uses the **first frame** in the weighted list.
    *   `targets`: All weighted frames.
    *   `pixelInterpolation`: `Auto`
    *   `clampingThreshold`: `0.30`
    *   `localDistortion`: `true`
    *   `upperScale`: `5`
    *   `hotPixelRemoval`: `1`
    *   `sensitivity`: `0.50`
    *   `peakResponse`: `0.50`
    *   `brightThreshold`: `3.00`
    *   `maxDistortion`: `0.60`
    *   `maximumStars`: `0` (Auto)
    *   `noiseReduction`: `0` (Disabled)
    *   `outputDirectory`: `PixInsight/registered`
    *   **Astrometric Solution**: Handled implicitly by alignment.

### 4. LocalNormalization
*   **Process**: `LocalNormalization`
*   **Parameters**:
    *   `referenceFrameGeneration`: `1` (Integration of best frames).
    *   `maximumIntegratedFrames`: `20`
    *   `targetItems`: All registered frames.
    *   `gridSize`: `4.0`
    *   `scaleEvaluationMethod`: `MultiScaleAnalysis` (Default/Implicit).
    *   `maxStars`: `24576`
    *   `minDetectionSNR`: `40`
    *   `allowClusteredSources`: `true`
    *   `noGuiding`: `false`
    *   `psfType`: `6` (Auto)
    *   `growthFactor`: `1.0`
    *   `lowClippingLevel`: `0.000045`
    *   `highClippingLevel`: `0.85`
    *   `evaluationCriteria`: `PSFSignalWeight`
    *   `outputDirectory`: `PixInsight/normalized`

### 5. ImageIntegration
*   **Process**: `ImageIntegration`
*   **Parameters**:
    *   `images`: All normalized (or registered) frames.
    *   `combination`: `Average` (Mean)
    *   `normalization`: `AdditiveWithScaling`
    *   `weightMode`: `PSFSignalWeight` (Critical for optimal SNR).
    *   `rejectionAlgorithm`: `WinsorizedSigmaClip`
    *   `sigmaLow`: `4.00`
    *   `sigmaHigh`: `3.00`
    *   `percentileLow`: `0.20`
    *   `percentileHigh`: `0.10`
    *   `generateIntegratedImage`: `true`
    *   `autoClipLowSample`: `true`
    *   `autoClipHighSample`: `true`
    *   `autoCrop`: `true` (Trims stacking edges).
    *   `outputDirectory`: `PixInsight/integrated`

---

## Calibration Verification

To ensure your frames are being calibrated with the correct flats:

1.  **Console Logging**:
    The script prints mapping information to the PixInsight console:
    ```text
    --- Processing Filter: H (24 frames) ---
    Calibration files for H:
      Bias: [Path]
      Dark: [Path]
      Flat: [Path]
    ```
2.  **Log File**:
    Check `launcher_debug.log` in the NebulaPilot root for the exact command-line arguments and mapping used.

3.  **Automatic Matching**:
    The logic ensures that the `masterFlatPath` is only set for a channel if the corresponding filter setting (e.g., `cal_flat_h`) has a path. This prevents cross-contamination of flats between filters.
