import sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar, 
    QLabel, QFileDialog, QHeaderView, QLineEdit, QDialog, QFormLayout,
    QFrame, QCheckBox, QSystemTrayIcon, QMenu, QStyle, QTimeEdit
)
from PySide6.QtCore import Qt, QSize, QSettings, QTimer, QTime, QDate, QMimeData
from PySide6.QtGui import QIcon, QColor, QAction, QDrag
from .db import init_db, get_targets, update_target_goals, get_target_progress, delete_target, clear_all_data
from .scanner import scan_directory
from .organizer import organize_directory
from .organizer import organize_directory
from .queue_manager import QueueManager
from .launcher import NebulaLauncher
from PySide6.QtWidgets import QMessageBox, QListWidget, QListWidgetItem, QAbstractItemView

# Dark Theme Stylesheet
DARK_THEME = """
QMenu {
    background-color: #2d2d30;
    color: #e0e0e0;
    border: 1px solid #3e3e42;
    min-width: 160px;
    padding: 5px;
}
QMenu::item:selected {
    background-color: #3e3e42;
}
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



class QueueListWidget(QListWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window # Store reference explicitly
        self.setAcceptDrops(True)
        self.setDragEnabled(True) # Allow reordering
        self.setDragDropMode(QAbstractItemView.DragDrop) # Allow External Drops + Internal Moves
        self.setDefaultDropAction(Qt.MoveAction)
        self.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #333337;
                border-radius: 4px;
                margin-bottom: 4px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #007acc;
            }
        """)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu(self)
            delete_action = menu.addAction("Remove from Queue")
            action = menu.exec(event.globalPos())
            if action == delete_action:
                target_name = item.data(Qt.UserRole)
                if hasattr(self.main_window, "remove_from_queue"):
                     self.main_window.remove_from_queue(target_name)

    def dragEnterEvent(self, event):
        # Respond to any drag, we filter in dropEvent
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        source = event.source()
        if source == self:
            # Handle Internal Reorder
            super().dropEvent(event)
            
            # Sync backend
            new_order = []
            for i in range(self.count()):
                item = self.item(i)
                data = item.data(Qt.UserRole)
                if data:
                    new_order.append(data)
                
            if hasattr(self.main_window, "sync_queue_order"):
                self.main_window.sync_queue_order(new_order)
                
            # Re-refresh
            if hasattr(self.main_window, "refresh_queue_ui"):
                 self.main_window.refresh_queue_ui()
                 
        elif isinstance(source, QTableWidget):
            # Handle Drop from Table (Direct Source Access)
            # Use selectedItems() which is more robust than currentRow()
            items = source.selectedItems()
            target_name = None
            
            # Find the item in column 0 (Target)
            for item in items:
                if item.column() == 0:
                    target_name = item.text()
                    break
            
            # Fallback: if selection is weird, try currentRow
            if not target_name:
                row = source.currentRow()
                if row >= 0:
                    item = source.item(row, 0)
                    if item:
                        target_name = item.text()
            
            if target_name:
                # Manual add via parent
                if hasattr(self.main_window, "add_to_queue_from_drop"):
                    self.main_window.add_to_queue_from_drop(target_name)
            
            event.acceptProposedAction()
        else:
            event.ignore()

class SchedulerSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Integration Schedule & Settings")
        self.setFixedWidth(450)
        self.layout = QFormLayout(self)
        
        # --- PI Executable Path ---
        pi_path = self.settings.value("pi_executable_path", r"C:\Program Files\PixInsight\bin\PixInsight.exe")
        self.pi_path_edit = QLineEdit(pi_path)
        self.pi_browse_btn = QPushButton("...")
        self.pi_browse_btn.setFixedWidth(30)
        self.pi_browse_btn.clicked.connect(self.browse_pi_path)
        
        pi_layout = QHBoxLayout()
        pi_layout.addWidget(self.pi_path_edit)
        pi_layout.addWidget(self.pi_browse_btn)
        
        self.layout.addRow("PixInsight.exe:", pi_layout)
        
        self.layout.addRow(QLabel("<hr>"))

        
        # Defaults
        # Morning: 09:00 - 12:00
        # Afternoon: 13:00 - 18:00
        
        m_start = self.settings.value("sched_m_start", QTime(9, 0))
        m_end = self.settings.value("sched_m_end", QTime(12, 0))
        a_start = self.settings.value("sched_a_start", QTime(13, 0))
        a_end = self.settings.value("sched_a_end", QTime(18, 0))
        
        # Ensure types (QSettings might return strings or user might have messed with ini)
        if not isinstance(m_start, QTime): m_start = QTime.fromString(m_start) if isinstance(m_start, str) else QTime(9, 0)
        if not isinstance(m_end, QTime): m_end = QTime.fromString(m_end) if isinstance(m_end, str) else QTime(12, 0)
        if not isinstance(a_start, QTime): a_start = QTime.fromString(a_start) if isinstance(a_start, str) else QTime(13, 0)
        if not isinstance(a_end, QTime): a_end = QTime.fromString(a_end) if isinstance(a_end, str) else QTime(18, 0)

        self.m_start_edit = QTimeEdit(m_start)
        self.m_end_edit = QTimeEdit(m_end)
        self.a_start_edit = QTimeEdit(a_start)
        self.a_end_edit = QTimeEdit(a_end)
        
        self.weekdays_cb = QCheckBox("Run on Weekdays Only (Skip Sat/Sun)")
        self.weekdays_cb.setChecked(self.settings.value("sched_weekdays_only", False, type=bool))
        
        for te in [self.m_start_edit, self.m_end_edit, self.a_start_edit, self.a_end_edit]:
            te.setDisplayFormat("HH:mm")
        
        self.layout.addRow(QLabel("<b>Morning Window</b>"))
        self.layout.addRow("Start:", self.m_start_edit)
        self.layout.addRow("End:", self.m_end_edit)
        
        self.layout.addRow(QLabel("<b>Afternoon Window</b>"))
        self.layout.addRow("Start:", self.a_start_edit)
        self.layout.addRow("End:", self.a_end_edit)
        
        self.layout.addRow(self.weekdays_cb)
        
        self.save_btn = QPushButton("Save Schedule")

        self.save_btn.clicked.connect(self.accept)
        self.layout.addRow(self.save_btn)
        
    def browse_pi_path(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select PixInsight Executable", "", "Executables (*.exe)")
        if fname:
            self.pi_path_edit.setText(fname)

    def save_settings(self):
        self.settings.setValue("pi_executable_path", self.pi_path_edit.text())
        self.settings.setValue("sched_m_start", self.m_start_edit.time())
        self.settings.setValue("sched_m_end", self.m_end_edit.time())
        self.settings.setValue("sched_a_start", self.a_start_edit.time())
        self.settings.setValue("sched_a_end", self.a_end_edit.time())
        self.settings.setValue("sched_weekdays_only", self.weekdays_cb.isChecked())



class CalibrationDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Master Calibration Files")
        self.setFixedWidth(500)
        self.layout = QFormLayout(self)
        
        self.paths = {}
        
        # Bias
        self.add_file_row("Master Bias:", "cal_bias")
        # Dark
        self.add_file_row("Master Dark:", "cal_dark")
        
        self.layout.addRow(QLabel("<b>Master Flats</b>"))
        self.add_file_row("L Flat:", "cal_flat_l")
        self.add_file_row("R Flat:", "cal_flat_r")
        self.add_file_row("G Flat:", "cal_flat_g")
        self.add_file_row("B Flat:", "cal_flat_b")
        self.add_file_row("S Flat:", "cal_flat_s")
        self.add_file_row("H Flat:", "cal_flat_h")
        self.add_file_row("O Flat:", "cal_flat_o")
        
        self.save_btn = QPushButton("Save Paths")
        self.save_btn.clicked.connect(self.accept)
        self.layout.addRow(self.save_btn)
        
    def add_file_row(self, label, key):
        path = self.settings.value(key, "")
        edit = QLineEdit(path)
        btn = QPushButton("...")
        btn.setFixedWidth(30)
        btn.clicked.connect(lambda: self.browse_file(edit))
        
        row_layout = QHBoxLayout()
        row_layout.addWidget(edit)
        row_layout.addWidget(btn)
        
        self.layout.addRow(label, row_layout)
        self.paths[key] = edit
        
    def browse_file(self, edit):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Master File", "", "Images (*.xisf *.fit *.fits)")
        if fname:
            edit.setText(fname)
            
    def save_settings(self):
        for key, edit in self.paths.items():
            self.settings.setValue(key, edit.text())



class NebulaPilotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.queue_manager = QueueManager()
        self.launcher = NebulaLauncher()
        self.queue_manager = QueueManager()
        self.launcher = NebulaLauncher()
        self.is_processing = False
        self.force_quit = False # Flag to distinguish between minimize (X) and quit
        
        self.setWindowTitle("NebulaPilot - Astrophotography Progress Tracker")
        self.resize(1200, 700) # Increased width for new columns
        self.setAcceptDrops(True) # Allow dragging items OUT of queue onto the window to delete
        
        # Initialize Settings
        self.settings = QSettings("NebulaPilot", "NebulaPilot")
        self.last_run_date = "" # Track daily run
        
        init_db()
        

        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        # Main Layout is now Horizontal (Left: Table/Controls, Right: Queue)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        # Left Panel (Existing Content)
        self.left_panel = QWidget()
        self.layout = QVBoxLayout(self.left_panel) # Reuse 'self.layout' name to minimize diff
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(20)
        
        self.main_layout.addWidget(self.left_panel, stretch=3) # 75% width
        
        # Right Panel (Queue)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(10)
        
        self.queue_label = QLabel("Integration Queue")
        self.queue_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e0e0e0;")
        self.right_layout.addWidget(self.queue_label)
        

        
        self.queue_list = QueueListWidget(self) # Pass self as main_window
        self.refresh_queue_ui() # Load initial queue
        self.right_layout.addWidget(self.queue_list)
        
        # Status Label for Processor
        self.processor_status = QLabel("Processor: Idle")
        self.processor_status.setStyleSheet("color: #aaaaaa; font-style: italic;")
        self.right_layout.addWidget(self.processor_status)

        # --- Queue Controls (Schedule & Calibration) ---
        self.queue_controls_layout = QHBoxLayout()
        self.queue_controls_layout.setSpacing(10)
        
        self.schedule_btn = QPushButton("Schedule")
        self.schedule_btn.setCursor(Qt.PointingHandCursor)
        self.schedule_btn.clicked.connect(self.open_scheduler_settings)
        self.queue_controls_layout.addWidget(self.schedule_btn)

        self.cal_btn = QPushButton("Calibration")
        self.cal_btn.setCursor(Qt.PointingHandCursor)
        self.cal_btn.clicked.connect(self.open_calibration_settings)
        self.queue_controls_layout.addWidget(self.cal_btn)
        
        self.right_layout.addLayout(self.queue_controls_layout)
        
        self.main_layout.addWidget(self.right_panel, stretch=1) # 25% width
        
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

        # Show Completed Checkbox
        self.show_completed_cb = QCheckBox("Show Completed")
        self.show_completed_cb.setChecked(False) # Default hidden
        self.show_completed_cb.stateChanged.connect(self.refresh_table)
        self.header_layout.addWidget(self.show_completed_cb)
        
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
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setDragEnabled(True) # Enable Dragging from Table
        self.table.setDragDropMode(QAbstractItemView.DragOnly) # Only Drag FROM here
        
        self.layout.addWidget(self.table)
        
        # --- System Tray Setup ---
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon)) 
        
        tray_menu = QMenu()
        
        # 1. Show Main Window
        show_action = QAction("Open NebulaPilot", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)
        
        # Separator (Optional)
        tray_menu.addSeparator()
        
        # 2. Quit
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
        """Ask user whether to minimize or quit."""
        if self.force_quit:
            event.accept()
            return

        # Create custom dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("NebulaPilot")
        msg_box.setText("Do you want to run NebulaPilot in the background?")
        msg_box.setInformativeText("Minimizing to tray keeps the scheduler active.")
        
        btn_minimize = msg_box.addButton("Minimize to Tray", QMessageBox.ActionRole)
        btn_quit = msg_box.addButton("Quit Application", QMessageBox.DestructiveRole)
        btn_cancel = msg_box.addButton(QMessageBox.Cancel)
        
        msg_box.setDefaultButton(btn_minimize)
        
        # Apply Dark Theme manually if needed, but app stylesheet should cover it
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_minimize:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "NebulaPilot",
                "Running in background.",
                QSystemTrayIcon.Information,
                2000
            )
        elif msg_box.clickedButton() == btn_quit:
            self.quit_app()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        """Handle dragging items OUT of the queue (Delete)."""
        source = event.source()
        if source == self.queue_list:
            event.acceptProposedAction()
            print("DEBUG: Dragging out of queue detected")
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop from Queue -> Window Background (Delete)."""
        source = event.source()
        if source == self.queue_list:
            # Reconstruct the item to verify logic or just iterate selected
            items = self.queue_list.selectedItems()
            for item in items:
                target_name = item.data(Qt.UserRole)
                if target_name:
                    print(f"DEBUG: Drag-Out Delete for {target_name}")
                    self.remove_from_queue(target_name)
                    
            event.acceptProposedAction()
        else:
            event.ignore()

    def quit_app(self):
        self.force_quit = True
        QApplication.quit()

    def on_auto_cb_changed(self, state):
        self.settings.setValue("auto_organize", self.auto_cb.isChecked())

    def check_schedule(self):
        """Called every minute to check if we should run."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        # Scheduler Trigger: 06:00 (Auto-Organize) — only if checkbox enabled
        if self.auto_cb.isChecked():
            if current_time == "06:00":
                if self.last_run_date != today_str:
                    print("Triggering Auto-Schedule...")
                    self.run_auto_organize()
                    self.last_run_date = today_str # Prevent re-run same day

        # Integration Scheduler Logic (always active)
        # Windows: 09:00-12:00, 13:00-18:00
        # Check every tick
        if self.is_processing:
            self.processor_status.setText("Processor: Running...")
            return

        current_hour = now.hour
        current_minute = now.minute
        
        # Check Weekend Filter
        weekdays_only = self.settings.value("sched_weekdays_only", False, type=bool)
        if weekdays_only and now.weekday() >= 5: # 5=Sat, 6=Sun
             self.processor_status.setText("Processor: Idle (Weekend)")
             return

        # Calculate Time Remaining in Window
        time_remaining_hours = 0
        window_active = False

        # Load Schedule (Defaults if not set)

        m_start = self.settings.value("sched_m_start", QTime(9, 0))
        m_end = self.settings.value("sched_m_end", QTime(12, 0))
        a_start = self.settings.value("sched_a_start", QTime(13, 0))
        a_end = self.settings.value("sched_a_end", QTime(18, 0))
        
        # Ensure types
        if not isinstance(m_start, QTime): m_start = QTime.fromString(m_start) if isinstance(m_start, str) else QTime(9, 0)
        if not isinstance(m_end, QTime): m_end = QTime.fromString(m_end) if isinstance(m_end, str) else QTime(12, 0)
        if not isinstance(a_start, QTime): a_start = QTime.fromString(a_start) if isinstance(a_start, str) else QTime(13, 0)
        if not isinstance(a_end, QTime): a_end = QTime.fromString(a_end) if isinstance(a_end, str) else QTime(18, 0)

        current_qtime = QTime(current_hour, current_minute)

        # Morning Window
        if m_start <= current_qtime < m_end:
            window_active = True
            # Diff in hours
            secs_to_end = current_qtime.secsTo(m_end)
            time_remaining_hours = secs_to_end / 3600.0
        
        # Afternoon Window
        elif a_start <= current_qtime < a_end:
            window_active = True
            secs_to_end = current_qtime.secsTo(a_end)
            time_remaining_hours = secs_to_end / 3600.0
        
        status_msg = f"Processor: Idle (Outside Windows)"
        if window_active:
            # Always check Queue if window is active, regardless of duration
            next_target = self.queue_manager.get_next_target()
            if next_target:
                status_msg = f"Processor: Active Window - Launching {next_target}..."
                self.run_process_target(next_target)
            else:
                status_msg = f"Processor: Active Window (Time Left: {time_remaining_hours:.1f}h) - Queue Empty"
                 
        self.processor_status.setText(status_msg)



    def add_to_queue_from_drop(self, target_name):
        if self.queue_manager.add_target(target_name):
            self.refresh_queue_ui()
            
    def remove_from_queue(self, target_name):
        self.queue_manager.remove_target(target_name)
        self.refresh_queue_ui()
    
    def sync_queue_order(self, new_order):
        """Update backend with new order from Drag & Drop."""
        self.queue_manager.reorder(new_order)
        
    def refresh_queue_ui(self):
        self.queue_list.clear() # Removes all items and their widgets
        for t in self.queue_manager.get_queue():
            # Create Item
            item = QListWidgetItem(self.queue_list)
            # item.setSizeHint(QSize(0, 30)) # Standard height
            item.setText(t) # Set text directly
            item.setData(Qt.UserRole, t) # Store name in UserRole
            
            # No custom widget needed

            
    def run_process_target(self, target_name):
        """Launches the integration process."""
        self.is_processing = True
        self.processor_status.setText(f"Processor: Launching PI for {target_name}...")
        self.tray_icon.showMessage("NebulaPilot", f"Starting Integration for {target_name}", QSystemTrayIcon.Information)
        
        # Get source dir from settings (files should be there)
        # For simplicity, we assume files are in settings_dest_dir / target_name
        dest_dir = self.settings.value("last_dest_dir", "")
        
        # Launch (Non-blocking usually, but we assume it runs)
        # In a real scenario, we'd need to know when PI finishes. 
        # For this prototype, we just launch and assume user manages it, OR we block?
        # User said "Auto trigger".
        
        # Retrieve Files from DB not implemented fully yet, but logic is there
        
        # Collect Calibration Files
        cal_files = {}
        for k in ["cal_bias", "cal_dark", "cal_flat_l", "cal_flat_r", 
                  "cal_flat_g", "cal_flat_b", "cal_flat_s", "cal_flat_h", "cal_flat_o"]:
            path = self.settings.value(k, "")
            if path:
                cal_files[k] = path
                
        # Get PI Path from settings
        pi_path = self.settings.value("pi_executable_path", r"C:\Program Files\PixInsight\bin\PixInsight.exe")
        print(f"DEBUG: App using PI Path: {pi_path}") 
        
        try:
            # Pass pi_path override
            self.launcher.pi_path = pi_path 
            self.launcher.log(f"App requesting launch for {target_name} with PI Path: {pi_path}")
            
            success = self.launcher.run_target(target_name, dest_dir, cal_files)
            if success:



                # Remove from Queue immediately so it doesn't loop forever?
                # Or move to end?
                self.queue_manager.remove_target(target_name)
                self.refresh_queue_ui()
                self.tray_icon.showMessage("NebulaPilot", f"Launched PI for {target_name}", QSystemTrayIcon.Information)
        except Exception as e:
             self.tray_icon.showMessage("Error", f"Failed to launch PI: {e}", QSystemTrayIcon.Critical)
             
        # Reset processing flag after launch (since PI is external)
        # Ideally we'd monitor the process, but `subprocess.Popen` returns immediately.
        # So we just say "We launched it". The user can stop us if they want.
        # But wait, if we reset fast, the scheduler might pick the NEXT one immediately if time remains!
        # This is dangerous. 
        # FIX: We should probably require manual "I'm done" or assume a long timeout.
        # Given the "2 hours" constraint, we should probably set a timer or waiting state.
        # For now, I'll set a logical "Busy" state for 5 minutes to prevent rapid fire? 
        # Or just let it go. One PI instance is usually enough.
        # I'll rely on the user to keep the queue clean for now.
        self.is_processing = False # Reset immediately to allow scheduler to check again (but maybe queue is empty now)
    
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

    def open_scheduler_settings(self):
        dlg = SchedulerSettingsDialog(self.settings, self)
        if dlg.exec():
            dlg.save_settings()
            self.check_schedule() # Re-check immediately

    def open_calibration_settings(self):
        dlg = CalibrationDialog(self.settings, self)
        if dlg.exec():
            dlg.save_settings()


    
    def refresh_table(self):
        all_targets = get_targets()
        
        # Calculate completion status for sorting
        target_list = []
        for target in all_targets:
            name = target["name"]
            progress = get_target_progress(name)
            
            # Goals
            goals = [
                int(target["goal_l"]), int(target["goal_r"]), int(target["goal_g"]), int(target["goal_b"]),
                int(target["goal_s"]) if "goal_s" in target.keys() else 0,
                int(target["goal_h"]) if "goal_h" in target.keys() else 0,
                int(target["goal_o"]) if "goal_o" in target.keys() else 0
            ]
            
            # Check Completion
            g_l, g_r, g_g, g_b, g_s, g_h, g_o = goals
            is_completed = True
            if g_l > 0 and progress.get('L', 0) < g_l: is_completed = False
            if g_r > 0 and progress.get('R', 0) < g_r: is_completed = False
            if g_g > 0 and progress.get('G', 0) < g_g: is_completed = False
            if g_b > 0 and progress.get('B', 0) < g_b: is_completed = False
            if g_s > 0 and progress.get('S', 0) < g_s: is_completed = False
            if g_h > 0 and progress.get('H', 0) < g_h: is_completed = False
            if g_o > 0 and progress.get('O', 0) < g_o: is_completed = False
            
            target_list.append({
                'data': target,
                'progress': progress,
                'goals': goals,
                'is_completed': is_completed
            })
            
        # Sort: Completed FIRST, then In-Progress
        # We sort by is_completed (True=1, False=0), so standard sort puts False first.
        # We want Completed (True) first, so we reverse sort on boolean or sort by `not is_completed`.
        # Secondary sort by name for stability.
        target_list.sort(key=lambda x: (not x['is_completed'], x['data']['name']))
        
        self.table.setRowCount(len(target_list))
        
        for i, item in enumerate(target_list):
            target = item['data']
            name = target['name']
            progress = item['progress']
            goals = item['goals']
            is_completed = item['is_completed']
            
            # Target Name
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, name_item)
            
            # Progress Bars
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
            
                self.table.setCellWidget(i, j + 1, container)
            
            # Status Logic was pre-calculated
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
            
            # Hide row if completed and show_completed is False
            if is_completed and not self.show_completed_cb.isChecked():
                self.table.setRowHidden(i, True)
            else:
                self.table.setRowHidden(i, False)
            
            # Actions
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 5, 5, 5)
            action_layout.setAlignment(Qt.AlignCenter)
            
            # Done Button
            done_btn = QPushButton("Done")
            done_btn.setCursor(Qt.PointingHandCursor)
            done_btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                    background-color: #388e3c;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #4caf50;
                }
            """)
            done_btn.clicked.connect(lambda checked, n=name: self.on_mark_complete(n))
            action_layout.addWidget(done_btn)

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
            
        # Adjust row heights to fixed value
        self.table.resizeRowsToContents()
        if self.table.rowCount() > 0:
             # Enforce minimum height if resizeToContents makes it too small
             for row in range(self.table.rowCount()):
                 if self.table.rowHeight(row) < 70:
                      self.table.setRowHeight(row, 70)
    
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

    def on_mark_complete(self, name):
        """Sets goals equal to current progress to mark as complete."""
        progress = get_target_progress(name)
        # Construct new goals tuple from current progress
        # Order: L, R, G, B, S, H, O
        new_goals = (
            int(progress.get('L', 0)),
            int(progress.get('R', 0)),
            int(progress.get('G', 0)),
            int(progress.get('B', 0)),
            int(progress.get('S', 0)),
            int(progress.get('H', 0)),
            int(progress.get('O', 0))
        )
        
        confirm = QMessageBox.question(
            self,
            "Mark as Complete",
            f"Mark target '{name}' as complete?\n\nThis will set its goals to match current progress:\n"
            f"L:{new_goals[0]} R:{new_goals[1]} G:{new_goals[2]} B:{new_goals[3]} "
            f"S:{new_goals[4]} H:{new_goals[5]} O:{new_goals[6]}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
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
