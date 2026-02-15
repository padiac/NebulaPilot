
import os
import shutil
from pathlib import Path
from datetime import datetime
from astropy.io import fits
from .scanner import get_fits_metadata

import re

def get_path_from_date_folder(file_path):
    """
    Try to find a date-like folder in the path and return the relative path starting from there.
    Supports YYYY-MM-DD, YYYYMMDD, YYYY_MM_DD.
    """
    parts = list(file_path.parts)
    # Regex for YYYY-MM-DD, YYYYMMDD, YYYY_MM_DD (simple validation)
    # Matches years 20xx or 19xx
    date_pattern = re.compile(r'^(19|20)\d{2}[-_\.]?(0[1-9]|1[0-2])[-_\.]?(0[1-9]|[12]\d|3[01])$')
    
    for i, part in enumerate(parts):
        if date_pattern.match(part):
            # Found the date folder. Return path starting from this part.
            return Path(*parts[i:])
            
    return None

def is_frame_good(header):
    """
    Check if a frame is good enough to be kept.
    Currently returns True for all valid FITS files.
    """
    # Example logic:
    # if header.get("EXPTIME", 0) < 60:
    #     return False
    return True

def get_organize_path(metadata, dest_root, source_root, is_good):
    """
    Determine the destination path for a file based on its metadata.
    Preserves directory structure starting from the Date folder downwards.
    """
    file_path = Path(metadata["path"])
    
    # Determine the structural part of the path we want to keep
    # Strategy: "Date Downwards"
    rel_path = get_path_from_date_folder(file_path)
    
    if rel_path is None:
        # Fallback: If no date folder found, try relative to source_root, else just filename
        try:
            rel_path = file_path.relative_to(source_root)
        except ValueError:
            rel_path = Path(file_path.name)

    # Standardize Target Name BEFORE determining destination
    target_name = metadata.get("target_name", "Unknown").replace(" ", "_").replace("/", "-")
            
    if not is_good:
        # Failed frames: Root / failed / Target / RelPath
        return Path(dest_root) / "failed" / target_name / rel_path
    
    # Good frames: Root / Target / RelPath
    return Path(dest_root) / target_name / rel_path


from datetime import datetime
from .db import init_db, add_target, add_frame
from .quality_check import ImageQualityAnalyzer
import csv
import numpy as np

def write_log_file(folder_path, log_records, group_reference=None):
    """
    Write log records to a CSV file in the specified folder.
    """
    if not folder_path.exists():
        folder_path.mkdir(parents=True, exist_ok=True)
        
    log_file = folder_path / "organizer_log.csv"
    
    # Check if file exists to write header
    file_exists = log_file.exists()
    
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            # Add Reference Info to Header if available
            header = ["Timestamp", "Filename", "Decision", "Reason", "StarCount", "FWHM", "Ellipticity", "BgMean", "BgRMS", "Ref_Stars", "Ref_FWHM"]
            writer.writerow(header)
        
        for record in log_records:
            metrics = record.get("metrics", {})
            
            ref_stars = ""
            ref_fwhm = ""
            if group_reference:
                ref_stars = group_reference.get("star_count", "")
                # group_reference["fwhm"] might be float
                ref_fwhm = f"{group_reference.get('fwhm', 0):.2f}"

            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                Path(record["path"]).name,
                record["decision"],
                record["reason"],
                metrics.get("star_count", ""),
                f"{metrics.get('fwhm', 0):.2f}",
                f"{metrics.get('ellipticity', 0):.2f}",
                f"{metrics.get('bg_mean', 0):.2f}",
                f"{metrics.get('bg_rms', 0):.2f}",
                ref_stars,
                ref_fwhm
            ])

def calculate_group_reference(records):
    """
    Calculate reference metrics (Star Count, FWHM) for a group of images.
    Strategy: Use robust statistics (e.g., 90th percentile for stars, median for FWHM).
    """
    if not records:
        return None
        
    # Extract metrics lists - ensure we only pull from records that actually have valid metrics
    star_counts = [r["metrics"]["star_count"] for r in records if r.get("metrics") and "star_count" in r["metrics"]]
    fwhms = [r["metrics"]["fwhm"] for r in records if r.get("metrics") and r["metrics"].get("fwhm", 0) > 0]
    
    if not star_counts:
        return None
        
    # Reference Star Count: 
    # Use 90th percentile (robust maximum) to avoid outliers but pick a "good" frame standard.
    # If very few frames, max is fine.
    ref_stars = float(np.percentile(star_counts, 90))
    
    # Reference FWHM:
    # Median is usually best for FWHM to ignore bad tracking/wind outliers.
    if fwhms:
        ref_fwhm = float(np.median(fwhms))
    else:
        ref_fwhm = 12.0 # Default fallback
        
    return {
        "star_count": ref_stars,
        "fwhm": ref_fwhm
    }

def evaluate_relative(record, reference):
    """
    Re-evaluate a single record against the group reference.
    Returns: (Decision String, Reason String)
    """
    metrics = record.get("metrics", {})
    
    # Safety check: if metrics are missing (e.g. analysis failed), stick with original decision
    if not metrics or "star_count" not in metrics:
        return record.get("initial_decision", "REJECT"), record.get("initial_reason", "Analysis failed / missing metrics")

    # 1. Absolute Failures (Keep these to filter out absolute garbage/clouds)
    # If star count is extremely low (< 5), it's probably just noise or clouds, regardless of reference.
    if metrics["star_count"] < 5:
        return "REJECT", "Start Count < 5 (Absolute Minimum)"

    # 2. Relative Star Count
    # Criterion: Must have at least X% of the reference star count.
    # Narrowband might have very few stars, so be generous.
    # Let's say 30%? If ref has 100 stars, and you have 20, that's suspicious.
    min_star_ratio = 0.3
    if metrics["star_count"] < (reference["star_count"] * min_star_ratio):
        return "REJECT", f"Star Count {metrics['star_count']} < {min_star_ratio:.0%} of Ref ({reference['star_count']:.1f})"
        
    # 3. Relative FWHM
    # Criterion: FWHM shouldn't be drastically worse than the median.
    # Allow 1.5x or 2.0x expansion (clouds/focus drift).
    max_fwhm_ratio = 1.6
    # Only check FWHM if we have a valid reference FWHM
    if reference["fwhm"] > 0 and metrics.get("fwhm", 0) > (reference["fwhm"] * max_fwhm_ratio):
        return "REJECT", f"FWHM {metrics['fwhm']:.2f} > {max_fwhm_ratio}x Ref ({reference['fwhm']:.2f})"
        
    return "ACCEPT", "Relative Pass"

def organize_directory(source_dir, dest_dir, dry_run=False, progress_callback=None, structure_callback=None, channel_callback=None):
    """
    Scans source_dir for FITS files, organizes them into dest_dir/Target/Date/Filter.
    Also performs image quality analysis (Pass 1: Collect Metrics, Pass 2: Evaluate Relative).
    
    Args:
        structure_callback (callable): func(structure_dict) - emits target/filter counts
        channel_callback (callable): func(target, filter, current_count) - updates specific bar
    """
    total_rejected = 0 
    
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    if not source_path.exists():
        print(f"Source directory {source_dir} does not exist.")
        return None

    print(f"Scanning {source_dir}...")
    
    analyzer = ImageQualityAnalyzer()
    
    # --- Pass 0: Quick Pre-Scan (Headers only) ---
    all_files = list(source_path.rglob("*.fit*"))
    total_files = len(all_files)
    
    # Key: (TargetName, FilterName) -> List of records (metadata only initially)
    groups = {} 
    
    # Structure for GUI: {target: {filter: count}}
    gui_structure = {}
    
    # Files ready for analysis
    pending_records_for_analysis = [] # List of references to record dicts in 'groups'
    
    processed_count = 0
    valid_files_count = 0
    
    if total_files == 0:
        if progress_callback: progress_callback(50, "No new files found. Checking cleanup...")
        print("No files found. Proceeding to cleanup.")
    else:
        # 1. Pre-Scan Headers (Fast)
        if progress_callback: progress_callback(0, "Scanning headers...")
        
        for i, file_path in enumerate(all_files):
            if not file_path.is_file():
                continue
            
            try:
                metadata = get_fits_metadata(file_path)
                if not metadata:
                    print(f"Skipping {file_path}: Metadata error")
                    continue
                    
                target = metadata.get("target_name", "Unknown").replace(" ", "_").replace("/", "-")
                filter_name = metadata.get("filter", "Unknown")
                
                group_key = (target, filter_name)
                
                if group_key not in groups:
                    groups[group_key] = []
                
                # Init record with just metadata for now
                record = {
                    "file_path": file_path,
                    "metadata": metadata,
                    # metrics/decision will be filled later
                }
                groups[group_key].append(record)
                
                # Update GUI structure
                if target not in gui_structure:
                    gui_structure[target] = {}
                gui_structure[target][filter_name] = gui_structure[target].get(filter_name, 0) + 1
                
                pending_records_for_analysis.append(record) # Store reference to the record
                valid_files_count += 1
                
                # Optional: Update progress for scan phase (0-10%)
                if progress_callback and i % 10 == 0:
                     percent = int((i / total_files) * 10)
                     progress_callback(percent, f"Scanning headers ({i}/{total_files})...")

            except Exception as e:
                print(f"Error reading header {file_path}: {e}")

        # Emit Structure to GUI
        if structure_callback:
            structure_callback(gui_structure)
            
        # 2. Analyze Images (Slow)
        # Pass 1 takes roughly 10-50% -> re-map to 10-50%
        
        # Track progress per channel for updates
        channel_progress = {} # (target, filter) -> count
        
        total_pending = len(pending_records_for_analysis)
        
        for i, record in enumerate(pending_records_for_analysis):
            file_path = record["file_path"]
            metadata = record["metadata"]
            
            # Update Main Progress (10-50%)
            percent = 10 + int((i / total_pending) * 40)
            status_msg = f"Analyzing {file_path.name}..."
            if progress_callback:
                progress_callback(percent, status_msg)
            
            print(f"Analyzing {file_path.name}...")

            try:
                # Perform Analysis
                analysis_result = analyzer.analyze_image(file_path)
                
                # Update the record with analysis results
                record["metrics"] = analysis_result["metrics"]
                record["initial_decision"] = analysis_result["decision"]
                record["initial_reason"] = analysis_result["reason"]
                
            except Exception as e:
                print(f"Analysis failed for {file_path}: {e}")
                # Mark as rejected if analysis fails
                record["metrics"] = {} # Empty metrics
                record["initial_decision"] = "REJECT"
                record["initial_reason"] = f"Analysis failed: {e}"
                total_rejected += 1
                
            # Update Channel Progress
            target = metadata.get("target_name", "Unknown").replace(" ", "_").replace("/", "-")
            filter_name = metadata.get("filter", "Unknown")
            key = (target, filter_name)
            channel_progress[key] = channel_progress.get(key, 0) + 1
            
            if channel_callback:
                channel_callback(target, filter_name, channel_progress[key])
                
    # Calculate Statistics (Initialize)
    stats = {
        "total_files": valid_files_count,
        "success_count": 0,
        "failed_count": 0,
        "reasons": {} # Track reasons for rejection
    }

    # --- Pass 2: Calculate Reference and Evaluate ---
    
    # Store logs to write later
    logs_to_write = {}

    total_groups = len(groups)
    current_group_idx = 0

    for (target, filter_name), records in groups.items():
        current_group_idx += 1
        
        # Approximate progress from 50% to 90% based on groups
        percent = 50 + int((current_group_idx / total_groups) * 40)
        
        status_msg = f"Processing Group: {target} ({filter_name})..."
        print(status_msg)
        if progress_callback:
            progress_callback(percent, status_msg)

        if not records:
            continue
            
        # 1. Compute Reference for this group
        reference = calculate_group_reference(records)
        if not reference:
            print(f"  -> Could not calculate reference (no stars?). Using absolute fallback.")
        else:
            print(f"  -> Reference: Stars={reference['star_count']:.1f}, FWHM={reference['fwhm']:.2f}")

        # 2. Re-Evaluate each file
        for record in records:
            # Decide
            if reference:
                decision, reason = evaluate_relative(record, reference)
            else:
                # Fallback to initial decision (Absolute Thresholds)
                decision = record["initial_decision"]
                reason = record["initial_reason"]
            
            is_good = (decision == "ACCEPT")
            
            # 3. Determine Paths
            source_file = record["file_path"]
            metadata = record["metadata"]
            
            # Destination path logic
            dest_file_path = get_organize_path(metadata, dest_dir, source_dir, is_good)
            
            # 4. Prepare Log Record
            log_entry = {
                "path": str(source_file),
                "dest_path": str(dest_file_path),
                "decision": decision,
                "reason": reason,
                "metrics": record["metrics"]
            }
            
            # Grouping for Log Writing (Target / StructureParent)
            # Similar to previous logic: identify the folder where this file ends up
            # Good: Dest/Target/RelPath
            # Bad:  Dest/failed/Target/RelPath
            # The LOG should go into: Dest/[failed]/Target/ParentOfRelPath
            
            # Extract relative parent for grouping log files
            # If we rely on dest_file_path.parent, that is exactly where the log should go?
            # Yes, usually "organizer_log.csv" sits right next to the images.
            # BUT, we want ONE log file per directory, and that directory might contain L, R, G, B files.
            # So (Target, Filter) grouping in Pass 1 vs (Directory) grouping for logs.
            # This is fine. We just key logs by dest_file_path.parent.
            
            log_folder = dest_file_path.parent
            if log_folder not in logs_to_write:
                logs_to_write[log_folder] = {
                    "records": [],
                    "reference": reference # Note: different filters in same folder might have different refs.
                    # This is tricky for headers. We might mix L and R refs in one CSV?
                    # Simplified: We just log the reference used for THAT file in the CSV row.
                }
            logs_to_write[log_folder]["records"].append(log_entry)

            # 5. Move File
            if dry_run:
                print(f"[DRY RUN] {decision}: {source_file.name} -> {dest_file_path} [{reason}]")
            else:
                dest_file_path.parent.mkdir(parents=True, exist_ok=True)
                # Use shutil.move for final production (clears source)
                shutil.move(str(source_file), str(dest_file_path))
                print(f"Moved {source_file.name} -> {dest_file_path} [{decision}]")
                
                # Update Statistics
                if is_good:
                    stats["success_count"] += 1
                else:
                    stats["failed_count"] += 1
                    stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1
                
                # Update DB (Only for Good files?)
                # If we fill DB with bad files, it might mess up stats.
                if is_good:
                    metadata["path"] = str(dest_file_path)
                    add_target(metadata["target_name"])
                    add_frame(metadata)

    # --- Write Logs ---
    if not dry_run:
        print("Writing logs...")
        for folder, data in logs_to_write.items():
            write_log_file(folder, data["records"], group_reference=None)

    # Clean up empty source directories after moving files
    if not dry_run:
        print("Cleaning up empty source directories...")
        
        # Define junk files that can be safely deleted if they are the only things left
        IGNORED_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}

    # Clean up empty source directories after moving files
    if not dry_run:
        print("Cleaning up empty source directories...")
        
        # Define junk files that can be safely deleted if they are the only things left
        IGNORED_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}

        def is_directory_effectively_empty(path):
            """
            Check if a directory is empty or contains only ignored system files.
            Returns True if it's safe to delete (effectively empty).
            """
            try:
                # List all items
                items = list(path.iterdir())
                # If completely empty
                if not items:
                    return True
                
                # Check if all items are files and are in the ignore list
                for item in items:
                    if item.is_dir():
                        return False # Contains a subdirectory, so not empty yet
                    if item.name not in IGNORED_FILES:
                        return False # Contains a non-junk file
                return True # Contains only junk files
            except Exception:
                return False

        import stat

        def remove_readonly(func, path, excinfo):
            """
            Error handler for shutil.rmtree.
            If the error is due to an access error (read only file)
            it attempts to add write permission and then retries.
            If the error is initializing the directory listing, or other errors,
            it falls through.
            """
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass


        # Run multiple passes to handle nested directory removal reliably
        # Sometimes deleting a child makes the parent empty, but os.walk order might miss it if structure is complex
        for _ in range(3):
            deleted_any = False
            # Use os.walk with topdown=False to delete children before parents
            for root, dirs, files in os.walk(source_dir, topdown=False):
                for name in dirs:
                    dir_to_check = Path(root) / name
                    
                    if is_directory_effectively_empty(dir_to_check):
                        try:
                            # Use rmtree to force delete even if read-only files inside
                            # This handles stubborn "Access Denied" caused by attributes
                            shutil.rmtree(dir_to_check, onerror=remove_readonly)
                            print(f"Removed empty directory: {dir_to_check}")
                            deleted_any = True
                        except Exception as e:
                            print(f"Failed to remove {dir_to_check}: {e}")
            
            if not deleted_any:
                break # No more work to do

    return stats



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        stats = organize_directory(sys.argv[1], sys.argv[2], dry_run=True)
        print(f"\nStats: Success={stats['success_count']}, Failed={stats['failed_count']}")
    else:
        print("Usage: python -m nebulapilot.organizer <source> <dest>")
