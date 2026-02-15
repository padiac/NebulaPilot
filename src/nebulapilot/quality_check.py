import os
import sys
import numpy as np
from astropy.io import fits
import warnings

# Try importing sep, handle if missing
try:
    import sep
except ImportError:
    sep = None

class ImageQualityAnalyzer:
    def __init__(self, thresholds=None):
        # Default conservative thresholds (loose enough to keep okay-ish frames)
        self.thresholds = {
            "min_stars": 20,          # Very low count = heavy cloud or cover closed
            "max_fwhm": 12.0,         # High FWHM = out of focus or wind shake (pixels)
            "max_ellipticity": 0.6,   # elongated stars = tracking error
            "max_bg_mean": 60000,     # Saturation check (16-bit ADU)
            "min_bg_mean": 0,         # Sanity check
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def analyze_image(self, file_path):
        """
        Analyze a FITS file and return metrics and acceptance decision.
        """
        if sep is None:
            return {
                "decision": "ACCEPT", # Fallback to accept if we can't check
                "reason": "sep_library_missing",
                "metrics": {}
            }

        try:
            with fits.open(file_path) as hdul:
                # Assuming data is in the primary HDU or first extension
                data = hdul[0].data
                if data is None and len(hdul) > 1:
                    data = hdul[1].data
                
                if data is None:
                    return {
                        "decision": "REJECT",
                        "reason": "no_image_data",
                        "metrics": {},
                        "path": str(file_path)
                    }

                # Ensure data is native byte order (SEP requirement) and float
                # FITS is big-endian, x86 is little-endian. .astype(float) usually handles this but
                # explicit byteswap might be needed if strictly using buffer protocol.
                # numpy.astype() generally returns native byte order.
                data = data.astype(float)
                
                # 1. Background Estimation
                try:
                    bkg = sep.Background(data)
                except Exception as bkg_err:
                     # This can happen if image is too small or flat
                    return {
                        "decision": "REJECT",
                        "reason": f"background_error: {bkg_err}",
                        "metrics": {},
                        "path": str(file_path)
                    }

                bg_mean = bkg.globalback
                bg_rms = bkg.globalrms
                
                # Subtract background for source detection
                data_sub = data - bkg.back()
                
                # 2. Source Extraction
                # threshold = 3.0 * sigma (standard)
                # minarea = 5 pixels
                objects = sep.extract(data_sub, 3.0, err=bkg.globalrms, minarea=5)
                
                star_count = len(objects)
                
                # 3. Calculate Metrics
                fwhm_median = 0.0
                ellipticity_median = 0.0

                if star_count > 0:
                    # SEP 'a' and 'b' are RMS parameters (sigma)
                    # For Gaussian profile: FWHM = 2.355 * sigma
                    # We average a and b for a single FWHM value per star
                    # Note: This is an approximation. IDL/PixInsight might use different fitting.
                    # Ideally we use calculate_fwhm from photutils, but SEP is faster here.
                    
                    # Filter out bad values (e.g. extremely large or small)
                    # objects['a'] and ['b'] are float32
                    
                    # Vectorized calculation
                    fwhms = 2.355 * (objects['a'] + objects['b']) / 2.0
                    
                    # Ellipticity: 1 - b/a
                    # Avoid division by zero
                    a_axis = objects['a']
                    b_axis = objects['b']
                    # mask where a > 0
                    valid_mask = a_axis > 0
                    
                    if np.any(valid_mask):
                        fwhms = fwhms[valid_mask]
                        # Ellipticity
                        dl = 1.0 - (b_axis[valid_mask] / a_axis[valid_mask])
                        
                        if len(fwhms) > 0:
                            fwhm_median = float(np.median(fwhms))
                            ellipticity_median = float(np.median(dl))

                metrics = {
                    "star_count": int(star_count),
                    "bg_mean": float(bg_mean),
                    "bg_rms": float(bg_rms),
                    "fwhm": float(fwhm_median),
                    "ellipticity": float(ellipticity_median),
                }
                
                # 4. Make Decision
                decision, reason = self._evaluate(metrics)
                
                # Convert boolean decision to "ACCEPT"/"REJECT" string for consistency
                decision_str = "ACCEPT" if decision else "REJECT"

                return {
                    "decision": decision_str,
                    "reason": reason,
                    "metrics": metrics,
                    "path": str(file_path)
                }

        except Exception as e:
            # Catch-all for corrupt files or SEP crashes
            return {
                "decision": "REJECT",
                "reason": f"analysis_crash: {str(e)}",
                "metrics": {},
                "path": str(file_path)
            }

    def _evaluate(self, metrics):
        # Always REJECT if star count is too low (Core logic for Clouds)
        if metrics["star_count"] < self.thresholds["min_stars"]:
            return False, f"Low star count: {metrics['star_count']} < {self.thresholds['min_stars']}"
            
        # REJECT if FWHM is too high (Blurry/Cloud/Tracking)
        # Only check if we actually have stars (count > 0)
        if metrics["star_count"] > 0 and metrics["fwhm"] > self.thresholds["max_fwhm"]:
             return False, f"High FWHM: {metrics['fwhm']:.2f} > {self.thresholds['max_fwhm']}"

        # REJECT if stars are too elliptical (Tracking)
        if metrics["star_count"] > 0 and metrics["ellipticity"] > self.thresholds["max_ellipticity"]:
             return False, f"High Ellipticity: {metrics['ellipticity']:.2f} > {self.thresholds['max_ellipticity']}"
            
        return True, "Good"
