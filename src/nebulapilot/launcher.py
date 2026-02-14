import shutil
import subprocess
import os
import json
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from copy import deepcopy
from .db import get_target_files


def _to_js_path(p):
    """Convert a Windows path to forward-slash format for PJSR."""
    return str(p).replace("\\", "/")


class NebulaLauncher:
    def __init__(self, pi_executable_path=r"D:\Program Files\PixInsight\bin\PixInsight.exe"):
        self.pi_path = pi_executable_path
        self.log_file = Path("launcher_debug.log").absolute()
        # WBPP script path (standard PI installation)
        self.wbpp_script_path = r"D:\Program Files\PixInsight\src\scripts\WeightedBatchPreprocessing\WeightedBatchPreprocessing.js"
        # WBPP settings template (user's saved XPSM)
        self.xpsm_template_path = Path(__file__).parent.parent.parent / "WBPP_SETTINGS.xpsm"

    def log(self, msg):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {msg}\n")
        except Exception as e:
            print(f"Logging failed: {e}")

    # ----------------------------------------------------------------
    # XPSM Parsing
    # ----------------------------------------------------------------
    def _parse_xpsm_params(self, xpsm_path):
        """Parse XPSM and return flat {key: value} dict of all WBPP parameters.
        
        The XPSM stores values inside a <table id="parameters"> with <tr><td> rows.
        Values are returned AS-IS (strings), since that's how fromJSONtest consumes them.
        """
        tree = ET.parse(xpsm_path)
        root = tree.getroot()
        ns = {'xpsm': 'http://www.pixinsight.com/xpsm'}

        instance = root.find('.//xpsm:instance', ns)
        if instance is None:
            instance = root.find('.//instance')
        if instance is None:
            raise ValueError(f"No <instance> found in XPSM: {xpsm_path}")

        params = {}
        table = instance.find('xpsm:table[@id="parameters"]', ns)
        if table is None:
            table = instance.find('table[@id="parameters"]')

        if table is not None:
            for row in (table.findall('xpsm:tr', ns) or table.findall('tr')):
                tds = row.findall('xpsm:td', ns) or row.findall('td')
                if len(tds) >= 2:
                    key = tds[0].text or ""
                    value = tds[1].text or ""
                    params[key] = value

        return params

    # ----------------------------------------------------------------
    # Fix groups data with correct file paths
    # ----------------------------------------------------------------
    def _fix_groups_paths(self, params, calibration_files, file_groups):
        """
        Rewrite the groups data in the testFile to use correct file paths.
        
        The XPSM template's groups contain hardcoded file paths from the
        original machine (e.g. F:/nina2/Calibration/...) which don't exist.
        WBPP loads these paths during importParameters() -> groupsFromStringData()
        and then tries to open them during pipeline execution, causing
        "File I/O Error: Invalid or empty file name".
        
        This method:
        1. Decodes the base64 groups JSON
        2. Updates calibration master paths (DARK/FLAT) to match user settings
        3. Removes any calibration groups that don't have a matching file
        4. Builds light frame groups from the actual DB files
        5. Re-encodes as base64
        
        WBPP group imageType values:
            0 = BIAS, 1 = DARK, 2 = FLAT, 3 = LIGHT
        """
        if "groups" not in params:
            self.log("WARNING: No groups in XPSM template")
            return
        
        try:
            groups = json.loads(base64.b64decode(params["groups"]))
        except Exception as e:
            self.log(f"ERROR decoding groups: {e}")
            return
        
        # --- Map calibration settings keys to filter names ---
        # cal_flat_l -> filter "l", cal_flat_h -> filter "h", etc.
        flat_map = {}  # filter_letter -> file_path
        for key, path in calibration_files.items():
            if key.startswith("cal_flat_") and path:
                filter_letter = key.replace("cal_flat_", "")
                flat_map[filter_letter] = path
        
        dark_path = calibration_files.get("cal_dark", "")
        bias_path = calibration_files.get("cal_bias", "")
        
        self.log(f"Calibration: dark={dark_path}, bias={bias_path}")
        self.log(f"Calibration flats: {flat_map}")
        
        # --- Update calibration groups ---
        updated_groups = []
        skipped_groups = []  # Track skipped groups for summary
        for g in groups:
            img_type = g.get("imageType", -1)
            
            if img_type == 0:  # BIAS
                if bias_path:
                    if os.path.exists(bias_path):
                        self._update_master_path(g, bias_path)
                        updated_groups.append(g)
                        self.log(f"  Updated BIAS group -> {bias_path}")
                    else:
                        skipped_groups.append(("BIAS", bias_path))
                        self.log(f"  WARNING: Skipping BIAS group — file does not exist: {bias_path}")
                else:
                    self.log(f"  Skipping BIAS group (no bias path set)")
                    
            elif img_type == 1:  # DARK
                if dark_path:
                    if os.path.exists(dark_path):
                        self._update_master_path(g, dark_path)
                        updated_groups.append(g)
                        self.log(f"  Updated DARK group -> {dark_path}")
                    else:
                        skipped_groups.append(("DARK", dark_path))
                        self.log(f"  WARNING: Skipping DARK group — file does not exist: {dark_path}")
                else:
                    self.log(f"  Skipping DARK group (no dark path set)")
                    
            elif img_type == 2:  # FLAT
                filt = g.get("filter", "")
                if filt in flat_map:
                    flat_path = flat_map[filt]
                    if os.path.exists(flat_path):
                        self._update_master_path(g, flat_path)
                        updated_groups.append(g)
                        self.log(f"  Updated FLAT group (filter={filt}) -> {flat_path}")
                    else:
                        skipped_groups.append((f"FLAT-{filt}", flat_path))
                        self.log(f"  WARNING: Skipping FLAT group (filter={filt}) — file does not exist: {flat_path}")
                else:
                    self.log(f"  Skipping FLAT group (filter={filt}, no matching cal file)")
                    
            elif img_type == 3:  # LIGHT - skip old ones, we'll add fresh below
                self.log(f"  Removing old LIGHT group (filter={g.get('filter', '?')})")
                continue
            else:
                updated_groups.append(g)
        
        # --- Log skipped groups summary ---
        if skipped_groups:
            self.log(f"  !! {len(skipped_groups)} calibration group(s) skipped due to missing files:")
            for grp_type, grp_path in skipped_groups:
                self.log(f"     - {grp_type}: {grp_path}")
            self.log(f"  !! Please update calibration paths in NebulaPilot > Calibration settings.")
        
        # --- Build light frame groups from actual files ---
        for filter_name, files in file_groups.items():
            if not files:
                continue
            light_group = self._build_light_group(filter_name, files)
            updated_groups.append(light_group)
            self.log(f"  Added LIGHT group: filter={filter_name}, {len(files)} files")
        
        # --- Re-encode ---
        if updated_groups:
            self.log(f"DEBUG: First group JSON: {json.dumps(updated_groups[0], indent=2)}")
        
        groups_json_str = json.dumps(updated_groups)
        params["groups"] = base64.b64encode(groups_json_str.encode("utf-8")).decode("ascii")
        self.log(f"Rebuilt groups: {len(updated_groups)} total groups")
    
    def _update_master_path(self, group, new_path):
        """Update the file path of a calibration master group and clear stale sidecar files."""
        js_path = _to_js_path(new_path)
        # Update the fileItems (there's typically exactly one for a master)
        for item in group.get("fileItems", []):
            item["filePath"] = js_path
            if "current" in item:
                item["current"]["default"] = js_path
            
            # Clear potential stale file references from the old template
            # If these point to non-existent files, WBPP throws File I/O Error
            item["localNormalizationFile"] = {}
            item["drizzleFile"] = {}
            item["processed"] = {}
            item["descriptor"] = {}
    
    # Known WBPP boolean parameters (from importParameters in engine.js)
    # These are read by getBoolean() which uses !!value — so the string
    # "false" must be converted to "" (falsy) to avoid misinterpretation.
    _BOOLEAN_PARAMS = {
        "saveFrameGroups", "smartNamingOverride", "detectMasterIncludingFullPath",
        "generateRejectionMaps", "darkIncludeBias", "optimizeDarks",
        "groupingKeywordsEnabled", "showAstrometricInfo", "imageRegistration",
        "cosmeticCorrection", "linearPatternSubtraction", "autocrop",
        "integrate", "localNormalization", "localNormalizationInteractiveMode",
        "localNormalizationGenerateImages", "localNormalizationPsfAllowClusteredSources",
        "subframeWeightingEnabled", "lightsLargeScaleRejectionLow",
        "lightsLargeScaleRejectionHigh", "flatsLargeScaleRejection",
        "usePipelineScript", "overscanEnabled",
        "overscanRegionEnabled_1", "overscanRegionEnabled_2",
        "overscanRegionEnabled_3", "overscanRegionEnabled_4",
        "platesolve", "platesolveFallbackManual", "distortionCorrection",
        "localDistortion", "allowClusteredSources", "useTriangleSimilarity",
        "imageSolverForceDefaults", "recombineRGB",
        "debayerActiveChannelR", "debayerActiveChannelG", "debayerActiveChannelB",
        "enableCompactGUI",
    }

    def _fixup_boolean_params(self, params):
        """Fix boolean string values for WBPP's getBoolean() which uses !!value.
        
        In JavaScript, !!"false" === true (non-empty string is truthy).
        Converting "false" → "" makes !!"" === false, which is correct.
        "true" is left as-is since !!"true" === true, which is correct.
        
        This specifically fixes usePipelineScript="false" being treated as true,
        which caused installEventScript("") → File I/O Error.
        """
        fixed = []
        for key in self._BOOLEAN_PARAMS:
            if key in params and params[key] == "false":
                params[key] = ""
                fixed.append(key)
        if fixed:
            self.log(f"  Fixed {len(fixed)} boolean params (false→''): {', '.join(fixed)}")

    def _build_light_group(self, filter_name, files):
        """
        Build a minimal LIGHT group for WBPP from a list of file paths.
        
        WBPP uses mode=1 (PRE) for calibration processing groups and 
        mode=2 (POST) for post-calibration groups. A single set of light
        files appears in BOTH a PRE group (for calibration) and a POST
        group (for registration/integration). We only need the PRE group
        here — WBPP reconstructs the POST groups automatically.
        """
        file_items = []
        for fp in files:
            js_path = _to_js_path(fp)
            file_items.append({
                "filePath": js_path,
                "imageType": 3,  # LIGHT
                "binning": 1,
                "filter": filter_name.lower(),
                "exposureTime": 300,  # Will be read from FITS header by WBPP
                "fileKeywords": {},
                "enabled": True,
                "size": {"width": 0, "height": 0},
                "matchingSizes": {},
                "createdWithSmartNamingEnabled": False,
                "solverParams": {},
                "isCFA": False,
                "isMaster": False,
                "keywords": {},
                "overscan": {
                    "enabled": False,
                    "overscan": [
                        {"enabled": False, "sourceRect": {}, "targetRect": {}}
                        for _ in range(4)
                    ],
                    "imageRect": {}
                },
                "processed": {},
                "current": {"default": js_path},
                "descriptor": {},
                "localNormalizationFile": {},
                "drizzleFile": {},
                "isReference": {"default": False}
            })
        
        return {
            "imageType": 3,  # LIGHT
            "binning": 1,
            "hasMaster": False,
            "exposureTime": 300,
            "filter": filter_name.lower(),
            "exposureTimes": [300],
            "optimizeMasterDark": False,
            "size": {"width": 0, "height": 0},
            "isCFA": False,
            "CFAPattern": 0,
            "debayerMethod": 2,
            "separateCFAFlatScalingFactors": False,
            "keywords": {},
            "mode": 1,  # PRE - for calibration
            "fileItems": file_items,
            "lightOutputPedestalMode": 1,
            "lightOutputPedestal": 0,
            "lightOutputPedestalLimit": 0.0001,
            "drizzleData": {
                "enabled": False,
                "scale": 1,
                "dropShrink": 0.9,
                "function": 0,
                "gridSize": 16
            },
            "isHidden": False,
            "isActive": True,
            "CCTemplate": "",
            "footerLengthForCurrentHeader": 0,
            "masterFiles": {},
            "forceNoDark": False,
            "forceNoFlat": False,
            "id": f"3_1_{filter_name.lower()}_300_mono__1_none_0x0",
            "__counter__": 1
        }

    # ----------------------------------------------------------------
    # JSON testFile generation
    # ----------------------------------------------------------------
    def _generate_test_file(self, target_name, output_dir, calibration_files={}, file_groups={}):
        """
        Generate a WBPP testFile JSON from the XPSM template.
        
        Strategy: 
        1. Load all settings from XPSM template
        2. Override outputDirectory and clear stale references
        3. Fix the groups data to use correct calibration and light file paths
        4. Write as .wbpptest JSON
        
        WBPP testFile format (from fromJSONtest in helper.js):
            {"data": {"key": value, ...}}
        """
        params = {}
        if self.xpsm_template_path.exists():
            params = self._parse_xpsm_params(self.xpsm_template_path)
            self.log(f"Loaded {len(params)} params from XPSM template")
        else:
            self.log("WARNING: No XPSM template found, using WBPP defaults")
            raise FileNotFoundError(f"XPSM template not found: {self.xpsm_template_path}")

        # Override output directory
        params["outputDirectory"] = _to_js_path(output_dir)

        # Clear stale references
        if "referenceImage" in params:
            del params["referenceImage"]
        if "bestFrameReferenceKeyword" in params:
            del params["bestFrameReferenceKeyword"]
        
        # Force auto reference method (0 = Auto) since we removed the manual reference
        params["bestFrameReferenceMethod"] = "0"
        
        params["executionCache"] = base64.b64encode(b"{}").decode("ascii")

        # --- FIX BOOLEAN STRINGS ---
        # WBPP's getBoolean() uses `!!value`, which makes the string "false"
        # TRUTHY (any non-empty string is truthy in JavaScript).
        # The XPSM template stores all values as strings, so "false" booleans
        # get misinterpreted as true. This caused usePipelineScript="false" to
        # be read as true, triggering installEventScript("") -> File I/O Error.
        #
        # Fix: convert "false" -> "" (!!""===false) and "true" -> "true" (ok).
        self._fixup_boolean_params(params)

        # Fix all file paths in groups data
        self._fix_groups_paths(params, calibration_files, file_groups)

        # --- Validate: count groups by type for pre-flight check ---
        try:
            final_groups = json.loads(base64.b64decode(params.get("groups", "")))
            light_count = sum(1 for g in final_groups if g.get("imageType") == 3)
            cal_count = sum(1 for g in final_groups if g.get("imageType") in (0, 1, 2))
            self.log(f"Pre-flight: {light_count} LIGHT group(s), {cal_count} calibration group(s)")
            if light_count == 0:
                self.log("ERROR: No LIGHT groups in testFile — WBPP will have nothing to process!")
            if cal_count == 0:
                self.log("WARNING: No calibration groups — WBPP will process lights without calibration.")
        except Exception as e:
            self.log(f"WARNING: Could not validate final groups: {e}")

        # Write testFile JSON
        test_data = {"data": params}
        
        test_file_path = Path(f"wbpp_{target_name}.wbpptest").absolute()
        with open(test_file_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2)

        self.log(f"Generated testFile: {test_file_path}")
        self.log(f"  outputDirectory: {params['outputDirectory']}")
        self.log(f"  VERSION: {params.get('VERSION', 'N/A')}")

        return test_file_path

    # ----------------------------------------------------------------
    # Launch WBPP
    # ----------------------------------------------------------------
    def generate_and_run(self, target_name, file_groups, calibration_files={}, output_base_dir=None):
        """
        Launch WBPP in automation mode using testFile approach.
        
        Uses the exact -r flag format from WBPP's own test runner:
        
            PixInsight.exe -n --automation-mode \
                -r="WBPP.js,automationMode=true,testFile=/path/to/config.wbpptest,outputDir=/path/to/out"
        
        The testFile contains ALL WBPP parameters including the groups data
        with correctly patched file paths for calibration masters and lights.
        
        NOTE: dir= and file= arguments are ONLY processed in no-testFile
        mode (WeightedBatchPreprocessing.js line 351-378). When a testFile
        is provided, all files MUST be specified inside the groups data.
        """
        # Determine output directory
        if output_base_dir:
            pi_out = Path(output_base_dir) / "PixInsight"
        else:
            first_files = list(file_groups.values())[0]
            pi_out = Path(first_files[0]).parent.parent / "PixInsight"

        if pi_out.exists():
            self.log(f"Cleaning up existing output directory: {pi_out}")
            try:
                shutil.rmtree(pi_out)
            except Exception as e:
                self.log(f"Warning: Failed to cleanup {pi_out}: {e}")

        pi_out.mkdir(parents=True, exist_ok=True)

        self.log(f"=== WBPP Automation for {target_name} ===")
        self.log(f"Output dir: {pi_out}")

        total_files = sum(len(v) for v in file_groups.values())
        self.log(f"Total light files from DB: {total_files}")

        for filter_name, files in file_groups.items():
            self.log(f"  Filter {filter_name}: {len(files)} files")

        # --- Generate testFile JSON from XPSM (with fixed paths) ---
        test_file = self._generate_test_file(target_name, pi_out, calibration_files, file_groups)

        # --- Build -r argument ---
        # NOTE: dir= is NOT used here because WBPP ignores it in testFile mode.
        # All files are embedded in the groups data inside the testFile.
        wbpp_js = _to_js_path(self.wbpp_script_path)
        test_file_js = _to_js_path(test_file)
        out_js = _to_js_path(pi_out)

        # --- Create a runner script to force PI to exit after completion ---
        # This is necessary because PI doesn't automatically exit after running
        # a script via -r, which prevents NebulaPilot from detecting completion.
        runner_file = test_file.with_suffix(".runner.js")
        with open(runner_file, "w", encoding="utf-8") as f:
            # Configure Gaia DR3 database path (USER PROVIDED)
            gaia_path = r"D:/Program Files/PixInsight/library/gaia"
            f.write(f'// Configure Gaia DR3 Database Path\n')
            f.write(f'try {{\n')
            f.write(f'   if (File.directoryExists("{gaia_path}")) {{\n')
            f.write(f'      Settings.write("StarCatalogs/Gaia/DR3/DatabaseFilePaths", ["{gaia_path}"]);\n')
            f.write(f'      console.writeln("nebulaPilot: Configured Gaia DR3 path: {gaia_path}");\n')
            f.write(f'   }} else {{\n')
            f.write(f'      console.warningln("nebulaPilot: Gaia path not found: {gaia_path}");\n')
            f.write(f'   }}\n')
            f.write(f'}} catch (e) {{\n')
            f.write(f'   console.criticalln("nebulaPilot: Error setting Gaia path: " + e.message);\n')
            f.write(f'}}\n\n')

            f.write(f'#include "{wbpp_js}"\n')
            # Note: CoreApplication.quit() is no longer a function in recent PixInsight versions.
            # When launched with --automation-mode, PixInsight will automatically exit
            # once the script execution finishes.
            
        runner_js = _to_js_path(runner_file)

        r_parts = [
            runner_js,
            "automationMode=true",
            f"testFile={test_file_js}",
            f"outputDir={out_js}",
        ]

        r_value = ",".join(r_parts)

        # Build shell command
        cmd_str = f'"{self.pi_path}" -n --automation-mode -r="{r_value}"'

        self.log(f"Command: {cmd_str}")
        print(f"Launching WBPP for {target_name}: {total_files} light frames")
        print(f"Output: {pi_out}")

        # Launch
        if not Path(self.pi_path).exists():
            self.log(f"ERROR: PI not found at {self.pi_path}")
            print(f"Error: PixInsight not found at {self.pi_path}")
            return False, [], None

        try:
            proc = subprocess.Popen(cmd_str, shell=True)
            self.log(f"Popen started, PID: {proc.pid}")
            return proc, [test_file, runner_file], pi_out
        except Exception as e:
            self.log(f"ERROR: {e}")
            import traceback
            self.log(traceback.format_exc())
            print(f"Error launching PixInsight: {e}")
            return False, [], None

    # Backwards-compatible alias
    def generate_script(self, target_name, file_groups, calibration_files={}, output_base_dir=None):
        return self.generate_and_run(target_name, file_groups, calibration_files, output_base_dir)

    def run_target(self, target_name, source_dir, calibration_files={}):
        """Retrieve files from DB and launch WBPP."""
        all_files = get_target_files(target_name)
        light_groups = all_files.get("Lights", {})

        if not light_groups:
            self.log(f"No light frames found for {target_name}")
            print(f"No light frames found for {target_name}")
            return False, [], None

        total_files = sum(len(v) for v in light_groups.values())
        self.log(f"Found {total_files} light frames for {target_name}")
        print(f"Found {total_files} light frames for {target_name}")

        # Determine output base based on actual file location to prevent duplicate folders
        # We prioritize the file's current path over the GUI's 'source_dir' setting
        if light_groups:
            first_files = list(light_groups.values())[0]
            # Assumes structure: Root/Target/Filter/File.fits
            # .parent = Filter folder, .parent.parent = Target folder
            output_base = Path(first_files[0]).parent.parent
        elif source_dir:
            output_base = Path(source_dir) / target_name
        else:
            output_base = Path.cwd() / target_name

        return self.generate_and_run(
            target_name, light_groups, calibration_files, output_base
        )
