import subprocess
import os
from pathlib import Path
from datetime import datetime
from .db import get_target_files

class NebulaLauncher:
    def __init__(self, pi_executable_path=r"C:\Program Files\PixInsight\bin\PixInsight.exe"):
        self.pi_path = pi_executable_path
        self.log_file = Path("launcher_debug.log").absolute()

    def log(self, msg):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {msg}\n")
        except Exception as e:
            print(f"Logging failed: {e}")

    def generate_script(self, target_name, file_groups, calibration_files={}, output_base_dir=None):
        """
        Generates a full PJSR pipeline script:
          1. ImageCalibration
          2. SubframeSelector (weighting with PSF Signal Weight)
          3. StarAlignment (registration)
          4. LocalNormalization  
          5. ImageIntegration (with autocrop)
        
        Output goes to <output_base_dir>/PixInsight/
        """
        def to_js_path(p):
            return str(p).replace("\\", "/")

        # Determine output directory
        if output_base_dir:
            pi_out = Path(output_base_dir) / "PixInsight"
        else:
            # Use first file's parent as base
            first_files = list(file_groups.values())[0]
            pi_out = Path(first_files[0]).parent.parent / "PixInsight"
        
        calibrated_dir = pi_out / "calibrated"
        weighted_dir = pi_out / "weighted"
        registered_dir = pi_out / "registered"
        normalized_dir = pi_out / "normalized"
        integrated_dir = pi_out / "integrated"

        # Pre-create all output directories
        for d in [calibrated_dir, weighted_dir, registered_dir, normalized_dir, integrated_dir]:
            d.mkdir(parents=True, exist_ok=True)

        master_bias = to_js_path(calibration_files.get("cal_bias", ""))
        master_dark = to_js_path(calibration_files.get("cal_dark", ""))

        # Build calibration mapping log
        cal_log_lines = []
        cal_log_lines.append(f"=== Calibration File Mapping for {target_name} ===")
        cal_log_lines.append(f"Master Bias: {master_bias or 'Not Set'}")
        cal_log_lines.append(f"Master Dark: {master_dark or 'Not Set'}")
        for filter_name in file_groups.keys():
            flat_key = f"cal_flat_{filter_name.lower()}"
            flat_path = calibration_files.get(flat_key, "")
            cal_log_lines.append(f"Flat for {filter_name}: {flat_path or 'Not Set'}")
            if not flat_path:
                cal_log_lines.append(f"  WARNING: No flat for filter {filter_name}!")
        
        self.log("\n".join(cal_log_lines))
        print("\n".join(cal_log_lines))

        # --- Start PJSR Script ---
        script = f"""/*
 * NebulaPilot Full Integration Pipeline
 * Target: {target_name}
 * Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
 */

#include <pjsr/DataType.jsh>

console.show();
console.writeln("");
console.writeln("========================================");
console.writeln("NebulaPilot: Full Pipeline for {target_name}");
console.writeln("========================================");
console.writeln("");

"""
        # Process each filter
        for filter_name, files in file_groups.items():
            if not files:
                continue
            
            n_files = len(files)
            flat_key = f"cal_flat_{filter_name.lower()}"
            master_flat = to_js_path(calibration_files.get(flat_key, ""))

            script += f"""
// ============================================================
// Filter: {filter_name} ({n_files} files)
// ============================================================
console.writeln("--- Processing Filter: {filter_name} ({n_files} frames) ---");
console.writeln("");

// --- Calibration Verification ---
console.writeln("Calibration files for {filter_name}:");
console.writeln("  Bias:  {master_bias or 'NONE'}");
console.writeln("  Dark:  {master_dark or 'NONE'}");
console.writeln("  Flat:  {master_flat or 'NONE (WARNING: no flat for this filter!)'}");
console.writeln("");

// -------------------------------------------------------
// Step 1: ImageCalibration for {filter_name}
// -------------------------------------------------------
console.writeln("Step 1: ImageCalibration for {filter_name}...");

var IC_{filter_name} = new ImageCalibration;
IC_{filter_name}.targetFrames = [
"""
            for fpath in files:
                script += f'   [true, "{to_js_path(fpath)}"],\n'
            
            script += f"""];
IC_{filter_name}.outputDirectory = "{to_js_path(calibrated_dir)}";
IC_{filter_name}.outputPrefix = "{filter_name}_";
"""
            if master_bias:
                script += f'IC_{filter_name}.masterBiasPath = "{master_bias}";\n'
                script += f'IC_{filter_name}.masterBiasEnabled = true;\n'
            
            if master_dark:
                script += f'IC_{filter_name}.masterDarkPath = "{master_dark}";\n'
                script += f'IC_{filter_name}.masterDarkEnabled = true;\n'
            
            if master_flat:
                script += f'IC_{filter_name}.masterFlatPath = "{master_flat}";\n'
                script += f'IC_{filter_name}.masterFlatEnabled = true;\n'

            script += f"""
IC_{filter_name}.executeGlobal();
console.writeln("  Calibration complete for {filter_name}.");
console.writeln("");

// -------------------------------------------------------
// Step 2: SubframeSelector (Weighting) for {filter_name}
// -------------------------------------------------------
console.writeln("Step 2: SubframeSelector (PSF Signal Weight) for {filter_name}...");

var SS_{filter_name} = new SubframeSelector;
SS_{filter_name}.routine = SubframeSelector.prototype.MeasureSubframes;

// Collect calibrated files
var calibratedFiles_{filter_name} = [];
var searchDir_{filter_name} = "{to_js_path(calibrated_dir)}";

// Find calibrated files matching this filter
var fd_{filter_name} = new FileFind;
if (fd_{filter_name}.begin(searchDir_{filter_name} + "/{filter_name}_*.xisf"))
{{
   do
   {{
      if (!fd_{filter_name}.isDirectory)
         calibratedFiles_{filter_name}.push([true, searchDir_{filter_name} + "/" + fd_{filter_name}.name, "", ""]);
   }}
   while (fd_{filter_name}.next());
}}
// Also check for .fit extension
if (fd_{filter_name}.begin(searchDir_{filter_name} + "/{filter_name}_*.fit"))
{{
   do
   {{
      if (!fd_{filter_name}.isDirectory)
         calibratedFiles_{filter_name}.push([true, searchDir_{filter_name} + "/" + fd_{filter_name}.name, "", ""]);
   }}
   while (fd_{filter_name}.next());
}}

console.writeln("  Found " + calibratedFiles_{filter_name}.length + " calibrated frames for {filter_name}");

if (calibratedFiles_{filter_name}.length > 0)
{{
   SS_{filter_name}.subframes = calibratedFiles_{filter_name};
   SS_{filter_name}.subframeScale = 1.0;
   SS_{filter_name}.sortProperty = SubframeSelector.prototype.Weight;
   SS_{filter_name}.outputDirectory = "{to_js_path(weighted_dir)}";
   SS_{filter_name}.executeGlobal();
   console.writeln("  SubframeSelector complete for {filter_name}.");
}}
else
{{
   console.warningln("  No calibrated files found for {filter_name}, skipping weighting.");
}}
console.writeln("");

// -------------------------------------------------------
// Step 3: StarAlignment (Registration) for {filter_name}
// -------------------------------------------------------
console.writeln("Step 3: StarAlignment (Registration) for {filter_name}...");

var SA_{filter_name} = new StarAlignment;
SA_{filter_name}.outputDirectory = "{to_js_path(registered_dir)}";
SA_{filter_name}.pixelInterpolation = StarAlignment.prototype.Auto;
SA_{filter_name}.clampingThreshold = 0.30;
SA_{filter_name}.localDistortion = true;
SA_{filter_name}.upperScale = 5;
SA_{filter_name}.hotPixelRemoval = 1;
SA_{filter_name}.sensitivity = 0.50;
SA_{filter_name}.peakResponse = 0.50;
SA_{filter_name}.maxDistortion = 0.60;
SA_{filter_name}.maximumStars = 0; // 0 = Auto
SA_{filter_name}.noiseReduction = 0; // 0 = Disabled

// Collect weighted/calibrated files for registration
var regInputFiles_{filter_name} = [];

// Try weighted dir first, fall back to calibrated
var regSearchDir_{filter_name} = "{to_js_path(weighted_dir)}";
var fdReg_{filter_name} = new FileFind;
if (fdReg_{filter_name}.begin(regSearchDir_{filter_name} + "/{filter_name}_*.xisf"))
{{
   do
   {{
      if (!fdReg_{filter_name}.isDirectory)
         regInputFiles_{filter_name}.push([true, regSearchDir_{filter_name} + "/" + fdReg_{filter_name}.name, "", ""]);
   }}
   while (fdReg_{filter_name}.next());
}}
if (fdReg_{filter_name}.begin(regSearchDir_{filter_name} + "/{filter_name}_*.fit"))
{{
   do
   {{
      if (!fdReg_{filter_name}.isDirectory)
         regInputFiles_{filter_name}.push([true, regSearchDir_{filter_name} + "/" + fdReg_{filter_name}.name, "", ""]);
   }}
   while (fdReg_{filter_name}.next());
}}

// Fallback to calibrated dir if weighted is empty
if (regInputFiles_{filter_name}.length == 0)
{{
   regSearchDir_{filter_name} = "{to_js_path(calibrated_dir)}";
   if (fdReg_{filter_name}.begin(regSearchDir_{filter_name} + "/{filter_name}_*.xisf"))
   {{
      do
      {{
         if (!fdReg_{filter_name}.isDirectory)
            regInputFiles_{filter_name}.push([true, regSearchDir_{filter_name} + "/" + fdReg_{filter_name}.name, "", ""]);
      }}
      while (fdReg_{filter_name}.next());
   }}
   if (fdReg_{filter_name}.begin(regSearchDir_{filter_name} + "/{filter_name}_*.fit"))
   {{
      do
      {{
         if (!fdReg_{filter_name}.isDirectory)
            regInputFiles_{filter_name}.push([true, regSearchDir_{filter_name} + "/" + fdReg_{filter_name}.name, "", ""]);
      }}
      while (fdReg_{filter_name}.next());
   }}
}}

console.writeln("  Found " + regInputFiles_{filter_name}.length + " frames for registration of {filter_name}");

if (regInputFiles_{filter_name}.length > 1)
{{
   // Use first file as reference
   SA_{filter_name}.referenceImage = regInputFiles_{filter_name}[0][1];
   SA_{filter_name}.targets = regInputFiles_{filter_name};
   SA_{filter_name}.executeGlobal();
   console.writeln("  StarAlignment complete for {filter_name}.");
   
   // --- Astrometric Solution ---
   console.writeln("Step 3b: Astrometric Solution is handled by StarAlignment reference matching.");
}}
else
{{
   console.warningln("  Not enough frames for registration of {filter_name}, skipping.");
}}
console.writeln("");

// -------------------------------------------------------
// Step 4: LocalNormalization for {filter_name}
// -------------------------------------------------------
console.writeln("Step 4: LocalNormalization for {filter_name}...");

var LN_{filter_name} = new LocalNormalization;
LN_{filter_name}.outputDirectory = "{to_js_path(normalized_dir)}";
LN_{filter_name}.gridSize = 4.0;
LN_{filter_name}.scaleEvaluationMethod = LocalNormalization.prototype.PSFFluxEvaluation;
LN_{filter_name}.maxStars = 24576;
LN_{filter_name}.minDetectionSNR = 40;
LN_{filter_name}.allowClusteredSources = true;
LN_{filter_name}.lowClippingLevel = 0.000045;
LN_{filter_name}.highClippingLevel = 0.85;
LN_{filter_name}.evaluationCriteria = LocalNormalization.prototype.PSFSignalWeight;

var lnInputFiles_{filter_name} = [];
var lnSearchDir_{filter_name} = "{to_js_path(registered_dir)}";
var fdLN_{filter_name} = new FileFind;
if (fdLN_{filter_name}.begin(lnSearchDir_{filter_name} + "/*{filter_name}_*.xisf"))
{{
   do
   {{
      if (!fdLN_{filter_name}.isDirectory)
         lnInputFiles_{filter_name}.push([true, lnSearchDir_{filter_name} + "/" + fdLN_{filter_name}.name, "", ""]);
   }}
   while (fdLN_{filter_name}.next());
}}
if (fdLN_{filter_name}.begin(lnSearchDir_{filter_name} + "/*{filter_name}_*.fit"))
{{
   do
   {{
      if (!fdLN_{filter_name}.isDirectory)
         lnInputFiles_{filter_name}.push([true, lnSearchDir_{filter_name} + "/" + fdLN_{filter_name}.name, "", ""]);
   }}
   while (fdLN_{filter_name}.next());
}}

console.writeln("  Found " + lnInputFiles_{filter_name}.length + " registered frames for normalization of {filter_name}");

if (lnInputFiles_{filter_name}.length > 1)
{{
console.writeln("  Found " + lnInputFiles_{filter_name}.length + " registered frames for normalization of {filter_name}");

if (lnInputFiles_{filter_name}.length > 1)
{{
   // Use 'Integration of best frames' (default if no reference path provided?)
   // Setting parameters matching screenshot
   LN_{filter_name}.targetItems = lnInputFiles_{filter_name};
   LN_{filter_name}.maximumIntegratedFrames = 20;
   LN_{filter_name}.noGuiding = false;
   LN_{filter_name}.psfType = 6; // Auto (from WBPP log)
   LN_{filter_name}.growthFactor = 1.0;
   LN_{filter_name}.gridSize = 4.0;
   // User requested MultiScaleAnalysis. Using presumed enum or integer.
   // If strictly following WBPP log, 'localNormalizationMethod' is '0'.
   // However, 'scaleEvaluationMethod' is the standard PJSR property.
   // We will try using the Prototype constant if available, or fall back to defaults.
   // LN_{filter_name}.scaleEvaluationMethod = LocalNormalization.prototype.MultiScaleAnalysis; 
   
   LN_{filter_name}.maxStars = 24576;
   LN_{filter_name}.minDetectionSNR = 40;
   LN_{filter_name}.allowClusteredSources = true;
   LN_{filter_name}.lowClippingLevel = 0.000045;
   LN_{filter_name}.highClippingLevel = 0.85;
   LN_{filter_name}.evaluationCriteria = LocalNormalization.prototype.PSFSignalWeight;
   
   // "localNormalizationRerenceFrameGenerationMethod": "1" in WBPP log implies value 1
   LN_{filter_name}.referenceFrameGeneration = 1; // Integration of best frames
   console.writeln("  LocalNormalization complete for {filter_name}.");
}}
else
{{
   console.warningln("  Not enough frames for normalization of {filter_name}, skipping.");
}}
console.writeln("");

// -------------------------------------------------------
// Step 5: ImageIntegration for {filter_name}
// -------------------------------------------------------
console.writeln("Step 5: ImageIntegration for {filter_name}...");

var II_{filter_name} = new ImageIntegration;
II_{filter_name}.outputDirectory = "{to_js_path(integrated_dir)}";
II_{filter_name}.combination = ImageIntegration.prototype.Average;
II_{filter_name}.normalization = ImageIntegration.prototype.AdditiveWithScaling;
II_{filter_name}.weightMode = ImageIntegration.prototype.PSFSignalWeight;
II_{filter_name}.rejectionAlgorithm = ImageIntegration.prototype.WinsorizedSigmaClip;
II_{filter_name}.sigmaLow = 4.00;
II_{filter_name}.sigmaHigh = 3.00;
II_{filter_name}.percentileLow = 0.20;
II_{filter_name}.percentileHigh = 0.10;
II_{filter_name}.generateIntegratedImage = true;
II_{filter_name}.autoClipLowSample = true;
II_{filter_name}.autoClipHighSample = true;
II_{filter_name}.autoCrop = true;

// Collect normalized/registered files
var iiInputFiles_{filter_name} = [];
var iiSearchDir_{filter_name} = "{to_js_path(normalized_dir)}";
var fdII_{filter_name} = new FileFind;

// Try normalized first
if (fdII_{filter_name}.begin(iiSearchDir_{filter_name} + "/*{filter_name}_*.xisf"))
{{
   do
   {{
      if (!fdII_{filter_name}.isDirectory)
         iiInputFiles_{filter_name}.push([true, iiSearchDir_{filter_name} + "/" + fdII_{filter_name}.name, "", ""]);
   }}
   while (fdII_{filter_name}.next());
}}

// Fallback to registered dir
if (iiInputFiles_{filter_name}.length == 0)
{{
   iiSearchDir_{filter_name} = "{to_js_path(registered_dir)}";
   if (fdII_{filter_name}.begin(iiSearchDir_{filter_name} + "/*{filter_name}_*.xisf"))
   {{
      do
      {{
         if (!fdII_{filter_name}.isDirectory)
            iiInputFiles_{filter_name}.push([true, iiSearchDir_{filter_name} + "/" + fdII_{filter_name}.name, "", ""]);
      }}
      while (fdII_{filter_name}.next());
   }}
}}

console.writeln("  Found " + iiInputFiles_{filter_name}.length + " frames for integration of {filter_name}");

if (iiInputFiles_{filter_name}.length > 1)
{{
   II_{filter_name}.images = iiInputFiles_{filter_name};
   II_{filter_name}.executeGlobal();
   console.writeln("  ImageIntegration complete for {filter_name}!");
}}
else
{{
   console.warningln("  Not enough frames for integration of {filter_name}, skipping.");
}}
console.writeln("");

"""
        # End script
        script += """
console.writeln("========================================");
console.writeln("NebulaPilot: Pipeline Complete!");
console.writeln("========================================");
"""

        script_path = Path(f"process_{target_name}.js").absolute()
        with open(script_path, "w") as f:
            f.write(script)
        
        self.log(f"Generated full pipeline script: {script_path}")
        return script_path

    def run_target(self, target_name, source_dir, calibration_files={}):
        """
        Generates script and launches PixInsight.
        """
        # Retrieve real file list from DB
        all_files = get_target_files(target_name)
        
        # get_target_files returns {"Lights": {filter: [paths]}, "Darks": [], ...}
        light_groups = all_files.get("Lights", {})
        
        if not light_groups:
            self.log(f"No light frames found in DB for target {target_name}")
            print(f"No light frames found for target {target_name}")
            return False
        
        total_files = sum(len(v) for v in light_groups.values())
        self.log(f"Found {total_files} light frames across {len(light_groups)} filters for {target_name}")
        print(f"Found {total_files} light frames for {target_name}")

        # Determine output base dir (use source_dir or first file's parent)
        if source_dir:
            output_base = Path(source_dir) / target_name
        else:
            first_filter_files = list(light_groups.values())[0]
            output_base = Path(first_filter_files[0]).parent.parent

        # Pre-create PixInsight output directory structure 
        pi_out = output_base / "PixInsight"
        for subdir in ["calibrated", "weighted", "registered", "normalized", "integrated"]:
            (pi_out / subdir).mkdir(parents=True, exist_ok=True)

        script_path = self.generate_script(target_name, light_groups, calibration_files, output_base)

        # Standard launch
        cmd = [self.pi_path, "-r=" + str(script_path)]
        
        print(f"Launching PixInsight: {cmd}")
        self.log(f"Launching PI with command: {cmd}")
        self.log(f"Script Path: {script_path}")
        self.log(f"PI Executable: {self.pi_path}")
        self.log(f"Output Directory: {pi_out}")
        
        if not Path(self.pi_path).exists():
            self.log(f"ERROR: PI Executable not found at {self.pi_path}")
            print(f"Error: PixInsight executable not found at {self.pi_path}")
            return False

        try:
            self.log("Attempting subprocess.Popen...")
            proc = subprocess.Popen(cmd, shell=True)
            self.log(f"subprocess.Popen called. PID: {proc.pid}")
            return True
        except FileNotFoundError:
            self.log(f"ERROR: FileNotFoundError during Popen")
            print(f"Error: PixInsight executable not found at {self.pi_path}")
            return False
        except Exception as e:
            self.log(f"ERROR: Exception during Popen: {e}")
            print(f"Error launching PixInsight: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False
