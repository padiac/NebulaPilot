# nebulaPilot 🌌

nebulaPilot is an **exposure progress management and automated organization tool** specifically designed for astrophotography enthusiasts. It automatically scans local FITS files, categorizes them by target, and tracks the cumulative exposure time for L/R/G/B channels, helping you intuitively understand whether each target has reached its preset exposure goals.

---

## 🚀 Key Features
- **Automated FITS Scanning**: Reads FITS Headers (OBJECT, FILTER, EXPTIME) to aggregate data automatically.
- **LRGB Progress Tracking**: Customize per-channel quotas for each target and view real-time progress bars.
- **GUI + CLI Dual Mode**:
  - **GUI**: Intuitive desktop interface for manual configuration and monitoring.
  - **CLI**: Perfect for automated scripts (e.g., Task Scheduler) for periodic silent scans.
- **Database Support**: Built with a local SQLite backend for lightweight and high-performance storage.
- **Software-ready Architecture**: Organized structure designed for direct compilation into Windows `.exe` executables.

---

## 🛠️ Installation

Python 3.10+ is recommended.

```bash
# Clone the repository and enter the directory
cd nebulapilot

# Install dependencies
pip install PySide6 astropy typer rich
```

---

## 📖 Usage Guide

### 1. Run the GUI (Desktop View)
```bash
# On Linux / WSL
PYTHONPATH=src python -m nebulapilot.app_gui

# On Windows PowerShell
$env:PYTHONPATH="src"
python -m nebulapilot.app_gui
```

### 2. Use the CLI (Command Line)
```bash
# Check exposure status for all targets
PYTHONPATH=src python -m nebulapilot.cli status

# Manually trigger a scan
PYTHONPATH=src python -m nebulapilot.cli scan /path/to/your/fits/folder
```

---

## 📦 Packaging (Windows .exe)

To package the project into a standalone Windows software:

1. **Install Packaging Tools**:
   ```bash
   pip install pyinstaller
   ```
2. **Run PyInstaller**:
   ```bash
   pyinstaller nebulaPilot.spec
   ```
3. **Generate Installer**:
   Use [Inno Setup](https://jrsoftware.org/isinfo.php) to compile the `installer.iss` script to get the `Setup.exe`.

---

## 📂 Project Structure
- `src/nebulapilot/`: Core source code.
  - `db.py`: Database operations and progress calculation.
  - `scanner.py`: FITS file scanning and metadata extraction.
  - `app_gui.py`: PySide6 interface implementation.
  - `cli.py`: Typer command-line implementation.
- `nebulaPilot.spec`: PyInstaller package configuration.
- `installer.iss`: Inno Setup installer script.
- `assets/`: Static resources like icons.

---

## ⚖️ License
MIT License
