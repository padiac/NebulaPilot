import sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar, 
    QLabel, QFileDialog, QHeaderView, QLineEdit, QDialog, QFormLayout,
    QFrame, QCheckBox, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, QSize, QSettings, QTimer, QTime, QDate
from PySide6.QtGui import QIcon, QColor, QAction
from .db import init_db, get_targets, update_target_goals, get_target_progress, delete_target, clear_all_data
from .scanner import scan_directory
from .organizer import organize_directory
from PySide6.QtWidgets import QMessageBox

# Dark Theme Stylesheet
DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #e0e0e0;
}
QWidget {
    font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 14px;
    color: #e0e0e0;
}
QTableWidget {
    background-color: #252526;
    gridline-color: #3e3e42;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    selection-background-color: #37373d;
    outline: none;
}
QHeaderView::section {
    background-color: #2d2d30;
    color: #e0e0e0;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #3e3e42;
    border-right: 1px solid #3e3e42;
    font-weight: bold;
}
QHeaderView::section:last {
    border-right: none;
}
QPushButton {
    background-color: #007acc;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #005f9e;
}
QPushButton:pressed {
    background-color: #004a80;
}
QPushButton:disabled {
    background-color: #3e3e42;
    color: #888888;
}
QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px;
    color: #e0e0e0;
    selection-background-color: #007acc;
}
QLineEdit:focus {
    border: 1px solid #007acc;
}
QProgressBar {
    background-color: #3c3c3c;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: white;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #007acc;
    border-radius: 4px;
    # ... existing styles ...
}
QCheckBox {
    spacing: 5px;
    color: #e0e0e0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QScrollBar:vertical {
    border: none;
    background: #2d2d30;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
    border-radius: 6px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QLabel#TitleLabel {
    font-size: 22px;
    font-weight: bold;
    color: #ffffff;
    padding: 10px 0;
}
"""

class GoalDialog(QDialog):
    def __init__(self, target_name, goals, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Goals for {target_name}")
        self.setFixedWidth(400)
        self.layout = QFormLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Ensure goals has 7 elements
        if len(goals) < 7:
             goals = goals + (0,) * (7 - len(goals))

        self.l_input = QLineEdit(str(int(goals[0])))
        self.r_input = QLineEdit(str(int(goals[1])))
        self.g_input = QLineEdit(str(int(goals[2])))
        self.b_input = QLineEdit(str(int(goals[3])))
        self.s_input = QLineEdit(str(int(goals[4])))
        self.h_input = QLineEdit(str(int(goals[5])))
        self.o_input = QLineEdit(str(int(goals[6])))
        
        self.layout.addRow("L Goal (frames):", self.l_input)
        self.layout.addRow("R Goal (frames):", self.r_input)
        self.layout.addRow("G Goal (frames):", self.g_input)
        self.layout.addRow("B Goal (frames):", self.b_input)
        self.layout.addRow("S Goal (frames):", self.s_input)
        self.layout.addRow("H Goal (frames):", self.h_input)
        self.layout.addRow("O Goal (frames):", self.o_input)
        
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(10)
        self.save_btn = QPushButton("Save")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        # Style cancel button differently (secondary action)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42; 
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #4e4e52;
            }
        """)

        self.buttons.addStretch()
        self.buttons.addWidget(self.cancel_btn)
        self.buttons.addWidget(self.save_btn)
        self.layout.addRow(self.buttons)

    def get_values(self):
        try:
            return (
                int(float(self.l_input.text())),
                int(float(self.r_input.text())),
                int(float(self.g_input.text())),
                int(float(self.b_input.text())),
                int(float(self.s_input.text())),
                int(float(self.h_input.text())),
                int(float(self.o_input.text()))
            )
        except ValueError:
            return None

class NebulaPilotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NebulaPilot - Astrophotography Progress Tracker")
        self.resize(1200, 700) # Increased width for new columns
        
        # Initialize Settings
        self.settings = QSettings("NebulaPilot", "NebulaPilot")
        self.last_run_date = "" # Track daily run
        
        init_db()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        
        # Header Area
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("Target Exposure Progress")
        self.title_label.setObjectName("TitleLabel")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        
        # Auto-Organize Checkbox
        self.auto_cb = QCheckBox("Auto-Organize (Daily 06:00)")
        self.auto_cb.setChecked(self.settings.value("auto_organize", False, type=bool))
        self.auto_cb.stateChanged.connect(self.on_auto_cb_changed)
        self.header_layout.addWidget(self.auto_cb)
        
        # Action Buttons
        self.scan_btn = QPushButton("Scan Directory")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setIcon(QIcon.fromTheme("system-search")) # Fallback if no icon
        self.scan_btn.clicked.connect(self.on_scan_clicked)
        self.header_layout.addWidget(self.scan_btn)

        self.organize_btn = QPushButton("Organize Files")
        self.organize_btn.setCursor(Qt.PointingHandCursor)
        self.organize_btn.setIcon(QIcon.fromTheme("folder-move"))
        self.organize_btn.clicked.connect(self.on_organize_clicked)
        self.header_layout.addWidget(self.organize_btn)
        
        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.header_layout.addWidget(separator)

        # Reset DB Button
        self.reset_btn = QPushButton("Reset DB")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #5d4037; 
                color: #e0e0e0;
                border: 1px solid #795548;
            }
            QPushButton:hover {
                background-color: #6d4c41;
            }
        """)
        self.reset_btn.clicked.connect(self.on_reset_db)
        self.header_layout.addWidget(self.reset_btn)
        
        self.layout.addWidget(self.header_frame)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(10) # Target, L, R, G, B, S, H, O, Status, Actions
        self.table.setHorizontalHeaderLabels([
            "Target", "L", "R", "G", "B", "S", "H", "O", "Status", "Actions"
        ])
        
        # Table Styling Properties
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True) # Styled by QSS
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.NoSelection) # Disable row selection (unless needed)
        
        self.layout.addWidget(self.table)
        
        # --- System Tray Setup ---
        self.tray_icon = QSystemTrayIcon(self)
        # Use a standard icon or fallback (assuming assets/icon.ico exists or using standard)
        # For now, let's use the window icon or a standard system icon
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon)) 
        
        tray_menu = QMenu()
        show_action = QAction("Show Main Window", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)
        
        run_now_action = QAction("Run Organization Now", self)
        run_now_action.triggered.connect(self.run_auto_organize)
        tray_menu.addAction(run_now_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Double click to show
        self.tray_icon.activated.connect(self.on_tray_activated)

        # --- Scheduler Timer ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_schedule)
        self.timer.start(60000) # Check every 60 seconds
        
        self.refresh_table()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def show_normal(self):
        self.show()
        self.setWindowState(Qt.WindowNoState)
        self.activateWindow()

    def closeEvent(self, event):
        """Minimize to tray instead of closing."""
        if self.tray_icon.isVisible():
            QMessageBox.information(self, "NebulaPilot", 
                                    "The application will keep running in the system tray to ensure auto-organization works.\n\n"
                                    "To quit completely, right-click the tray icon and select 'Quit'.")
            self.hide()
            self.tray_icon.showMessage(
                "NebulaPilot",
                "Running in background. Double-click tray icon to restore.",
                QSystemTrayIcon.Information,
                3000
            )
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        QApplication.quit()

    def on_auto_cb_changed(self, state):
        self.settings.setValue("auto_organize", self.auto_cb.isChecked())

    def check_schedule(self):
        """Called every minute to check if we should run."""
        if not self.auto_cb.isChecked():
            return

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        # Scheduler Trigger: 06:00
        if current_time == "06:00":
            if self.last_run_date != today_str:
                print("Triggering Auto-Schedule...")
                self.run_auto_organize()
                self.last_run_date = today_str # Prevent re-run same day
    
    def run_auto_organize(self):
        source_dir = self.settings.value("last_source_dir", "")
        dest_dir = self.settings.value("last_dest_dir", "")
        
        if not source_dir or not dest_dir:
            self.tray_icon.showMessage("Auto-Organize Failed", "Source or Destination directory not set.", QSystemTrayIcon.Warning)
            return
            
        self.tray_icon.showMessage("NebulaPilot", "Auto-Organizing files...", QSystemTrayIcon.Information)
        
        # Run organization
        try:
            organize_directory(source_dir, dest_dir)
            self.refresh_table()
            self.tray_icon.showMessage("NebulaPilot", "Organization Complete! Database Updated.", QSystemTrayIcon.Information)
        except Exception as e:
            self.tray_icon.showMessage("Error", f"Organization failed: {str(e)}", QSystemTrayIcon.Critical)

    def refresh_table(self):
        targets = get_targets()
        self.table.setRowCount(len(targets))
        
        for i, target in enumerate(targets):
            target_data = target
            name = target["name"]
            # Db returns row, accessing by index or name. 
            # We updated db.py to return 7 goal columns.
            # Handle case where db might return fewer columns if migration didn't happen (though it should have)
            goals = [
                int(target["goal_l"]), int(target["goal_r"]), int(target["goal_g"]), int(target["goal_b"]),
                int(target["goal_s"]) if "goal_s" in target.keys() else 0,
                int(target["goal_h"]) if "goal_h" in target.keys() else 0,
                int(target["goal_o"]) if "goal_o" in target.keys() else 0
            ]
            
            progress = get_target_progress(name)
            
            # Target Name
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, name_item)
            
            # Progress Bars for L, R, G, B, S, H, O
            filters = ["L", "R", "G", "B", "S", "H", "O"]
            for j, f in enumerate(filters):
                goal = goals[j]
                current = int(progress.get(f, 0))
                
                container = QWidget()
                vbox = QVBoxLayout(container)
                vbox.setContentsMargins(4, 5, 4, 5) # Tighter margins
                vbox.setSpacing(2)
                
                p_bar = QProgressBar()
                p_bar.setFixedHeight(12) 
                
                # Logic for status labels and progress bars
                label_text = f"{current} / {goal}"
                percent = 0
                
                if goal == 0:
                    # If goal is 0, consider it 100% done (not needed)
                    percent = 100
                    p_bar.setValue(100)
                    # Use a grey color to indicate 'not needed' but 'done'
                    p_bar.setStyleSheet("QProgressBar::chunk { background-color: #555555; }")
                    label_text = "N/A"
                elif goal > 0:
                    percent = min(100, int((current / goal) * 100))
                    p_bar.setValue(percent)
                    # Dynamic color for progress bars
                    color = "#cccccc" # Default L
                    if f == 'R': color = "#e57373"
                    elif f == 'G': color = "#81c784"
                    elif f == 'B': color = "#64b5f6"
                    elif f == 'S': color = "#a52a2a" # Brown/Red for Sulphur
                    elif f == 'H': color = "#d32f2f" # Deep Red for Hydrogen
                    elif f == 'O': color = "#00bcd4" # Cyan/Teal for Oxygen
                    
                    p_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
                
                label = QLabel(label_text) # Integer display
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet("font-size: 10px; color: #aaaaaa;")
                
                vbox.addWidget(p_bar)
                vbox.addWidget(label)
                
                self.table.setCellWidget(i, j + 1, container)
            
            # Use progress dict from DB or calculate if missing (DB function does it)
            progress = get_target_progress(name)
            
            # Goals
            g_l = target_data['goal_l']
            g_r = target_data['goal_r']
            g_g = target_data['goal_g']
            g_b = target_data['goal_b']
            g_s = target_data['goal_s']
            g_h = target_data['goal_h']
            g_o = target_data['goal_o']
            
            # Check if COMPLETED
            # Condition: For every channel, if goal > 0, then progress must be >= goal.
            is_completed = True
            
            # L
            if g_l > 0 and progress['L'] < g_l: is_completed = False
            # RGB
            if g_r > 0 and progress['R'] < g_r: is_completed = False
            if g_g > 0 and progress['G'] < g_g: is_completed = False
            if g_b > 0 and progress['B'] < g_b: is_completed = False
            # SHO
            if g_s > 0 and progress['S'] < g_s: is_completed = False
            if g_h > 0 and progress['H'] < g_h: is_completed = False
            if g_o > 0 and progress['O'] < g_o: is_completed = False

            if is_completed:
                status_text = "COMPLETED"
                status_color = "#98c379" # Green
            else:
                status_text = "IN_PROGRESS"
                status_color = "#e5c07b" # Yellow/Orange

            # 8. Status (Dynamic)
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 8, status_item)
            
            # Actions
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 5, 5, 5)
            action_layout.setAlignment(Qt.AlignCenter)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setCursor(Qt.PointingHandCursor)
            # Smaller button for actions
            edit_btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 12px;
                    font-size: 12px;
                    background-color: #4e4e52;
                }
                QPushButton:hover {
                    background-color: #5e5e62;
                }
            """)
            edit_btn.clicked.connect(lambda checked, n=name, g=goals: self.on_edit_goals(n, g))
            action_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Del")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 12px;
                    font-size: 12px;
                    background-color: #d32f2f;
                }
                QPushButton:hover {
                    background-color: #ef5350;
                }
            """)
            delete_btn.clicked.connect(lambda checked, n=name: self.on_delete_target(n))
            action_layout.addWidget(delete_btn)
            
            self.table.setCellWidget(i, 9, action_widget)
            
        # Adjust row heights
        self.table.verticalHeader().setDefaultSectionSize(70)
    
    def on_delete_target(self, name):
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete target '{name}'?\nThis will remove it from the database tracking.\n(Files on disk will NOT be deleted)",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            delete_target(name)
            self.refresh_table()

    def on_edit_goals(self, name, goals):
        dialog = GoalDialog(name, goals, self)
        if dialog.exec():
            new_goals = dialog.get_values()
            if new_goals:
                update_target_goals(name, new_goals)
                self.refresh_table()

    def on_reset_db(self):
        confirm = QMessageBox.warning(
            self,
            "Reset Database",
            "Are you sure you want to delete ALL data (both targets and frame records)?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            clear_all_data()
            self.refresh_table()
            QMessageBox.information(self, "Database Reset", "All data has been cleared.")

    def on_scan_clicked(self):
        last_dir = self.settings.value("last_scan_dir", "")
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", last_dir)
        
        if dir_path:
            self.settings.setValue("last_scan_dir", dir_path)
            scan_directory(dir_path)
            self.refresh_table()

    def on_organize_clicked(self):
        last_source = self.settings.value("last_source_dir", "")
        source_dir = QFileDialog.getExistingDirectory(self, "Select Source Directory (Incoming Files)", last_source)
        
        if not source_dir:
            return
        self.settings.setValue("last_source_dir", source_dir)

        last_dest = self.settings.value("last_dest_dir", "")
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Destination Directory (Organized Storage)", last_dest)
        
        if not dest_dir:
            return
        self.settings.setValue("last_dest_dir", dest_dir)

        confirm = QMessageBox.question(
            self, 
            "Confirm Organization", 
            f"Are you sure you want to move files from:\n{source_dir}\n\nTo:\n{dest_dir}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            organize_directory(source_dir, dest_dir)
            self.refresh_table()
            QMessageBox.information(self, "Success", "File organization complete! Database updated.")

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME) # Apply global dark theme
    # Ensure tooltips and tray icon visible
    app.setQuitOnLastWindowClosed(False) # KEEP APP RUNNING for tray
    
    window = NebulaPilotGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
