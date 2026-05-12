"""PySide6 GUI for ACS-AI-Image-Reproducer."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig
from .key_store import KeyStoreError, load_api_key, save_api_key
from .providers import GEMINI_IMAGE_MODEL, OPENAI_IMAGE_MODEL, GeminiImageProvider, OpenAIImageProvider
from .tasks import GenerationRequest, GenerationResult, GenerationWorker


PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"

SIZE_OPTIONS = [
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "1920x1080",
    "1080x1920",
]
QUALITY_OPTIONS = ["low", "medium", "high"]


class MainWindow(QMainWindow):
    """Main GUI window."""

    def __init__(self) -> None:
        super().__init__()
        self.config = AppConfig()

        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(300)
        self._eta_timer.timeout.connect(self._tick_eta)

        self._network_stage_start = 0.0
        self._network_expected = 0.0
        self._latest_generated_path: Path | None = None
        self._latest_result: GenerationResult | None = None

        self.setWindowTitle("ACS-AI-Image-Reproducer")
        self._build_ui()
        self._configure_window_bounds()
        self._apply_styles()
        self._load_initial_state()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        title = QLabel("ACS-AI-Image-Reproducer")
        title.setObjectName("AppTitle")
        subtitle = QLabel(
            "Generate and compare AI reproductions from a local reference image. "
            "Approve to replace an existing file only when you like the result."
        )
        subtitle.setWordWrap(True)

        toggles_row = QHBoxLayout()
        self.show_keys_toggle = QCheckBox("Show API Keys & Validation")
        self.show_keys_toggle.toggled.connect(self._toggle_keys_panel)
        self.show_test_view_toggle = QCheckBox("Test View (show logs)")
        self.show_test_view_toggle.toggled.connect(self._toggle_test_view)
        self.open_generated_button = QPushButton("Open Generated")
        self.open_generated_button.clicked.connect(self._open_latest_image)
        self.reset_window_button = QPushButton("Reset Window")
        self.reset_window_button.clicked.connect(self._reset_window_geometry)
        toggles_row.addWidget(self.show_keys_toggle)
        toggles_row.addWidget(self.show_test_view_toggle)
        toggles_row.addWidget(self.open_generated_button)
        toggles_row.addWidget(self.reset_window_button)
        toggles_row.addStretch(1)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(toggles_row)

        self.result_box = self._build_result_panel()
        main_layout.addWidget(self.result_box, 5)

        self.action_bar = self._build_action_bar()
        main_layout.addWidget(self.action_bar)

        self.top_grid = QGridLayout()
        self.top_grid.setColumnStretch(0, 4)
        self.top_grid.setColumnStretch(1, 0)
        main_layout.addLayout(self.top_grid, 3)

        self.generation_box = self._build_generation_panel()
        self.credentials_box = self._build_credentials_panel()
        self.top_grid.addWidget(self.generation_box, 0, 0)
        self.top_grid.addWidget(self.credentials_box, 0, 1)

    def _build_generation_panel(self) -> QGroupBox:
        box = QGroupBox("Generation Settings")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Gemini (Default)", PROVIDER_GEMINI)
        self.provider_combo.addItem("OpenAI", PROVIDER_OPENAI)
        self.provider_combo.currentIndexChanged.connect(self._sync_model_label)

        self.model_label = QLabel()

        ref_row = QHBoxLayout()
        self.reference_path_input = QLineEdit()
        self.reference_path_input.setPlaceholderText("Select reference image (.png/.jpg/.jpeg/.webp)")
        browse_ref_btn = QPushButton("Browse")
        browse_ref_btn.clicked.connect(self._choose_reference_image)
        ref_row.addWidget(self.reference_path_input, 1)
        ref_row.addWidget(browse_ref_btn)

        output_row = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Choose output folder")
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_dir_input, 1)
        output_row.addWidget(browse_output_btn)

        self.output_name_input = QLineEdit()
        self.output_name_input.setPlaceholderText("Optional generated filename (candidate)")

        self.replace_mode_checkbox = QCheckBox("Enable replacement workflow after approval")
        self.replace_mode_checkbox.setChecked(True)
        self.replace_mode_checkbox.toggled.connect(self._toggle_replace_options)

        replace_target_row = QHBoxLayout()
        self.replace_target_input = QLineEdit()
        self.replace_target_input.setPlaceholderText("Select EXISTING local image to replace after approval")
        browse_target_btn = QPushButton("Browse")
        browse_target_btn.clicked.connect(self._choose_replace_target)
        replace_target_row.addWidget(self.replace_target_input, 1)
        replace_target_row.addWidget(browse_target_btn)

        self.preserve_filename_checkbox = QCheckBox("Use target's same filename/path when approving replace")
        self.preserve_filename_checkbox.setChecked(True)

        self.keep_backup_checkbox = QCheckBox("Keep backup of old image before replacing")
        self.keep_backup_checkbox.setChecked(True)

        self.size_combo = QComboBox()
        self.size_combo.addItems(SIZE_OPTIONS)
        self.size_combo.setCurrentText("1536x1024")

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_OPTIONS)
        self.quality_combo.setCurrentText("high")

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Describe what to reproduce from the reference image: subject, framing, lighting, textures, color fidelity..."
        )
        self.prompt_input.setMinimumHeight(88)
        self.prompt_input.setMaximumHeight(110)

        columns = QHBoxLayout()
        columns.setSpacing(16)

        left_form = QFormLayout()
        left_form.setHorizontalSpacing(10)
        left_form.setVerticalSpacing(6)
        left_form.addRow("Provider", self.provider_combo)
        left_form.addRow("Fixed model", self.model_label)
        left_form.addRow("Reference image", self._wrap_layout(ref_row))
        left_form.addRow("Output folder", self._wrap_layout(output_row))
        left_form.addRow("Output candidate name", self.output_name_input)
        left_form.addRow("Target size", self.size_combo)
        left_form.addRow("Quality", self.quality_combo)

        right_form = QFormLayout()
        right_form.setHorizontalSpacing(10)
        right_form.setVerticalSpacing(6)
        right_form.addRow("Replace mode", self.replace_mode_checkbox)
        right_form.addRow("Image to replace", self._wrap_layout(replace_target_row))
        right_form.addRow("Filename behavior", self.preserve_filename_checkbox)
        right_form.addRow("Backup old image", self.keep_backup_checkbox)
        right_form.addRow("Prompt", self.prompt_input)

        left_panel = QWidget()
        left_panel.setLayout(left_form)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        right_panel = QWidget()
        right_panel.setLayout(right_form)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        columns.addWidget(left_panel, 1)
        columns.addWidget(right_panel, 1)
        layout.addLayout(columns)
        box.setMaximumHeight(315)
        return box

    def _build_credentials_panel(self) -> QGroupBox:
        box = QGroupBox("API Keys (system keyring)")
        layout = QVBoxLayout(box)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.Password)
        self.openai_key_input.setPlaceholderText("OpenAI API key")
        openai_buttons = QHBoxLayout()
        openai_save = QPushButton("Save")
        openai_save.clicked.connect(lambda: self._save_key(PROVIDER_OPENAI))
        openai_validate = QPushButton("Validate")
        openai_validate.clicked.connect(lambda: self._validate_key(PROVIDER_OPENAI))
        openai_buttons.addWidget(openai_save)
        openai_buttons.addWidget(openai_validate)

        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.Password)
        self.gemini_key_input.setPlaceholderText("Gemini API key")
        gemini_buttons = QHBoxLayout()
        gemini_save = QPushButton("Save")
        gemini_save.clicked.connect(lambda: self._save_key(PROVIDER_GEMINI))
        gemini_validate = QPushButton("Validate")
        gemini_validate.clicked.connect(lambda: self._validate_key(PROVIDER_GEMINI))
        gemini_buttons.addWidget(gemini_save)
        gemini_buttons.addWidget(gemini_validate)

        form.addRow("OpenAI key", self.openai_key_input)
        form.addRow("", self._wrap_layout(openai_buttons))
        form.addRow("Gemini key", self.gemini_key_input)
        form.addRow("", self._wrap_layout(gemini_buttons))
        layout.addLayout(form)

        note = QLabel(
            "Keys are securely saved in OS keyring.\n"
            f"OpenAI fixed model: {OPENAI_IMAGE_MODEL}\n"
            f"Gemini fixed model: {GEMINI_IMAGE_MODEL}"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return box

    def _build_result_panel(self) -> QGroupBox:
        box = QGroupBox("Preview & Result")
        layout = QVBoxLayout(box)

        preview_container = QFrame()
        preview_container.setObjectName("PreviewContainer")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(8, 8, 8, 8)

        self.preview_label = QLabel("Generated image preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(420)
        preview_layout.addWidget(self.preview_label)

        self.output_path_label = QLabel("Output candidate: --")
        self.output_path_label.setWordWrap(True)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Execution log...")
        self.log_box.setMinimumHeight(160)

        layout.addWidget(preview_container, 5)
        layout.addWidget(self.output_path_label)
        layout.addWidget(self.log_box, 2)
        return box

    def _build_action_bar(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.generate_button = QPushButton("Generate / Reproduce Image")
        self.generate_button.setObjectName("GenerateButton")
        self.generate_button.clicked.connect(self._start_generation)

        self.reject_button = QPushButton("Reject & Regenerate")
        self.reject_button.clicked.connect(self._reject_generated)
        self.reject_button.setEnabled(False)

        self.approve_button = QPushButton("Approve Replace")
        self.approve_button.clicked.connect(self._approve_replacement)
        self.approve_button.setEnabled(False)

        controls.addWidget(self.generate_button, 1)
        controls.addWidget(self.reject_button, 1)
        controls.addWidget(self.approve_button, 1)
        layout.addLayout(controls)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready.")
        self.eta_label = QLabel("ETA: --")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.eta_label, 0, Qt.AlignRight)
        layout.addLayout(status_row)
        return wrapper

    def _configure_window_bounds(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 900)
            return

        available = screen.availableGeometry()
        self.setMaximumSize(available.width(), available.height())
        target_width = min(available.width(), 1380)
        target_height = min(available.height(), 920)
        self.resize(target_width, target_height)
        self._center_on_screen(available)

    def _reset_window_geometry(self) -> None:
        self._configure_window_bounds()
        self._log("Window position and size reset to centered defaults.")

    def _center_on_screen(self, available_geometry) -> None:
        frame = self.frameGeometry()
        frame.moveCenter(available_geometry.center())
        self.move(frame.topLeft())

    def _open_latest_image(self) -> None:
        if self._latest_generated_path is None or not self._latest_generated_path.exists():
            QMessageBox.information(self, "No generated image", "Generate an image first, then open it.")
            return

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(self._latest_generated_path)], check=False)
            elif os.name == "nt":
                os.startfile(str(self._latest_generated_path))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(self._latest_generated_path)], check=False)
            self._log(f"Opened generated image: {self._latest_generated_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open image error", f"Could not open generated image: {exc}")

    def _wrap_layout(self, layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget { font-size: 13px; }
            #AppTitle { font-size: 24px; font-weight: 700; }
            QGroupBox {
                border: 1px solid #3f4753;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px 0 4px;
            }
            #GenerateButton { min-height: 34px; font-weight: 600; }
            #PreviewContainer {
                border: 1px dashed #5f6875;
                border-radius: 8px;
            }
            """
        )

    def _load_initial_state(self) -> None:
        self.output_dir_input.setText(str(self.config.get_last_output_dir()))
        self.provider_combo.setCurrentIndex(0)
        self._sync_model_label()
        self._toggle_keys_panel(False)
        self._toggle_test_view(False)
        self._toggle_replace_options(True)

        openai_key = load_api_key(PROVIDER_OPENAI)
        if openai_key:
            self.openai_key_input.setText(openai_key)

        gemini_key = load_api_key(PROVIDER_GEMINI)
        if gemini_key:
            self.gemini_key_input.setText(gemini_key)

    def _toggle_keys_panel(self, enabled: bool) -> None:
        self.credentials_box.setVisible(enabled)
        self.top_grid.setColumnStretch(0, 4 if not enabled else 3)
        self.top_grid.setColumnStretch(1, 0 if not enabled else 2)

    def _toggle_test_view(self, enabled: bool) -> None:
        self.log_box.setVisible(enabled)

    def _toggle_replace_options(self, enabled: bool) -> None:
        self.replace_target_input.setEnabled(enabled)
        self.preserve_filename_checkbox.setEnabled(enabled)
        self.keep_backup_checkbox.setEnabled(enabled)

    def _sync_model_label(self) -> None:
        provider = self.provider_combo.currentData()
        self.model_label.setText(GEMINI_IMAGE_MODEL if provider == PROVIDER_GEMINI else OPENAI_IMAGE_MODEL)

    def _choose_reference_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select reference image",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg *.webp)",
        )
        if file_path:
            self.reference_path_input.setText(file_path)

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            self.output_dir_input.text().strip() or str(Path.home()),
        )
        if folder:
            self.output_dir_input.setText(folder)

    def _choose_replace_target(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select existing image to replace",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg *.webp)",
        )
        if file_path:
            self.replace_target_input.setText(file_path)

    def _current_key_input(self, provider: str) -> QLineEdit:
        return self.openai_key_input if provider == PROVIDER_OPENAI else self.gemini_key_input

    def _save_key(self, provider: str) -> None:
        key_input = self._current_key_input(provider)
        value = key_input.text().strip()
        if not value:
            QMessageBox.warning(self, "Missing key", f"Please enter a {provider} API key.")
            return
        try:
            save_api_key(provider, value)
        except KeyStoreError as exc:
            QMessageBox.critical(self, "Key storage error", str(exc))
            return
        self._log(f"Saved {provider} key in system keyring.")
        QMessageBox.information(self, "Saved", f"{provider.capitalize()} API key saved securely.")

    def _validate_key(self, provider: str) -> None:
        key_input = self._current_key_input(provider)
        key_value = key_input.text().strip() or load_api_key(provider)
        if not key_value:
            QMessageBox.warning(self, "Missing key", f"No {provider} key available to validate.")
            return
        try:
            if provider == PROVIDER_OPENAI:
                OpenAIImageProvider().validate_key(key_value)
            else:
                GeminiImageProvider().validate_key(key_value)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Validation failed", str(exc))
            self._log(f"{provider} key validation failed: {exc}")
            return
        self._log(f"{provider} key validation succeeded.")
        QMessageBox.information(self, "Validation success", f"{provider.capitalize()} API key is valid.")

    def _start_generation(self) -> None:
        if self._thread is not None:
            QMessageBox.warning(self, "In progress", "A generation is already running.")
            return

        request = self._build_request()
        if request is None:
            return

        self._latest_generated_path = None
        self._latest_result = None
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting...")
        self.eta_label.setText("ETA: calculating...")
        self.output_path_label.setText("Output candidate: --")
        self.preview_label.setText("Generating preview...")
        self.preview_label.setPixmap(QPixmap())
        self.generate_button.setEnabled(False)
        self.approve_button.setEnabled(False)
        self.reject_button.setEnabled(False)

        self._thread = QThread(self)
        self._worker = GenerationWorker(request, self.config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def _build_request(self) -> GenerationRequest | None:
        provider = self.provider_combo.currentData()
        prompt = self.prompt_input.toPlainText().strip()
        reference_path = self.reference_path_input.text().strip()
        output_dir = self.output_dir_input.text().strip()
        output_name = self.output_name_input.text().strip()
        size = self.size_combo.currentText()
        quality = self.quality_combo.currentText()

        if not reference_path:
            QMessageBox.warning(self, "Missing reference image", "Please select a reference image first.")
            return None
        if not output_dir:
            QMessageBox.warning(self, "Missing output folder", "Please select an output folder.")
            return None
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Please enter a prompt to guide image reproduction.")
            return None

        if self.replace_mode_checkbox.isChecked() and not self.replace_target_input.text().strip():
            QMessageBox.warning(
                self,
                "Missing replacement target",
                "Replacement mode is enabled. Please select the existing local image to replace.",
            )
            return None

        return GenerationRequest(
            provider=provider,
            prompt=prompt,
            reference_image=Path(reference_path).expanduser(),
            output_dir=Path(output_dir).expanduser(),
            output_name=output_name,
            size=size,
            quality=quality,
        )

    def _on_progress(self, payload: dict) -> None:
        percent = int(payload.get("percent", 0))
        message = str(payload.get("message", "Working..."))
        stage = str(payload.get("stage", ""))
        self.progress_bar.setValue(max(0, min(100, percent)))
        self.status_label.setText(message)
        if stage == "network_wait":
            self._network_stage_start = float(payload.get("network_started", time.monotonic()))
            self._network_expected = float(payload.get("network_expected", 30.0))
            self._eta_timer.start()
        elif stage in {"save", "done"}:
            self._eta_timer.stop()
            self.eta_label.setText("ETA: finalizing...")

    def _tick_eta(self) -> None:
        if not self._network_stage_start or not self._network_expected:
            return
        elapsed = max(0.0, time.monotonic() - self._network_stage_start)
        ratio = min(0.99, elapsed / max(1.0, self._network_expected))
        mapped_percent = int(30 + (ratio * 50))
        if mapped_percent > self.progress_bar.value():
            self.progress_bar.setValue(mapped_percent)
        eta_seconds = max(0, int(self._network_expected - elapsed))
        self.eta_label.setText(f"ETA: ~{eta_seconds}s")

    def _on_finished(self, result: GenerationResult) -> None:
        self._eta_timer.stop()
        self.progress_bar.setValue(100)
        self._latest_generated_path = result.output_path
        self._latest_result = result
        self.eta_label.setText(f"Elapsed: {result.elapsed_seconds:.1f}s")
        self.output_path_label.setText(f"Output candidate: {result.output_path}")
        self._set_preview(result.output_path)

        self._log(
            f"Generation completed with {result.provider} ({result.model}) in {result.elapsed_seconds:.2f}s\n"
            f"Candidate saved: {result.output_path}"
        )

        if self.replace_mode_checkbox.isChecked():
            self.status_label.setText("Candidate ready. Approve to replace or reject to regenerate.")
            self.approve_button.setEnabled(True)
            self.reject_button.setEnabled(True)
        else:
            self.status_label.setText("Completed successfully.")
            QMessageBox.information(self, "Done", f"Image generated and saved to:\n{result.output_path}")

    def _on_failed(self, message: str) -> None:
        self._eta_timer.stop()
        self.status_label.setText("Generation failed.")
        self.eta_label.setText("ETA: --")
        self._log(f"Error: {message}")
        QMessageBox.critical(self, "Generation error", message)

    def _cleanup_worker(self) -> None:
        self.generate_button.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _reject_generated(self) -> None:
        if self._latest_generated_path is None:
            return
        self.status_label.setText("Candidate rejected. You can regenerate as many times as needed.")
        self._log(f"Rejected candidate: {self._latest_generated_path}")
        self.approve_button.setEnabled(False)
        self.reject_button.setEnabled(False)

    def _approve_replacement(self) -> None:
        if self._latest_generated_path is None:
            QMessageBox.warning(self, "No candidate", "Generate a candidate image first.")
            return

        target = Path(self.replace_target_input.text().strip()).expanduser()
        if not target.exists():
            QMessageBox.warning(self, "Target missing", "Selected image to replace does not exist.")
            return

        try:
            if self.keep_backup_checkbox.isChecked():
                backup = self._build_backup_path(target)
                shutil.copy2(target, backup)
                self._log(f"Backup created: {backup}")

            if self.preserve_filename_checkbox.isChecked():
                self._write_candidate_as_target_format(self._latest_generated_path, target)
                final_path = target
            else:
                final_path = target.parent / self._latest_generated_path.name
                shutil.copy2(self._latest_generated_path, final_path)

            self.status_label.setText("Replacement approved and applied.")
            self.output_path_label.setText(f"Final image: {final_path}")
            self._latest_generated_path = final_path
            self._set_preview(final_path)
            self._log(f"Replacement applied at: {final_path}")
            QMessageBox.information(self, "Approved", f"Image replacement completed:\n{final_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Replace error", f"Could not apply replacement: {exc}")
            self._log(f"Replacement failed: {exc}")
            return

        self.approve_button.setEnabled(False)
        self.reject_button.setEnabled(False)

    def _build_backup_path(self, target: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return target.with_name(f"{target.stem}.backup_{stamp}{target.suffix}")

    def _write_candidate_as_target_format(self, generated_path: Path, target_path: Path) -> None:
        target_suffix = target_path.suffix.lower()
        if target_suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            shutil.copy2(generated_path, target_path)
            return

        raw = generated_path.read_bytes()
        with Image.open(io.BytesIO(raw)) as img:
            if target_suffix in {".jpg", ".jpeg"}:
                converted = img.convert("RGB")
                converted.save(target_path, format="JPEG", quality=95, subsampling=0, optimize=True)
            elif target_suffix == ".png":
                converted = img.convert("RGBA")
                converted.save(target_path, format="PNG", compress_level=6)
            elif target_suffix == ".webp":
                converted = img.convert("RGBA")
                converted.save(target_path, format="WEBP", quality=95, method=6)

    def _set_preview(self, output_path: Path) -> None:
        if not output_path.exists():
            self.preview_label.setText("Preview unavailable.")
            self.preview_label.setPixmap(QPixmap())
            return

        pixmap = QPixmap(str(output_path))
        if pixmap.isNull():
            self.preview_label.setText("Preview unavailable for this format.")
            self.preview_label.setPixmap(QPixmap())
            return

        scaled = pixmap.scaled(
            self.preview_label.width(),
            self.preview_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._latest_generated_path:
            self._set_preview(self._latest_generated_path)

    def _log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{timestamp}] {text}")


def run() -> None:
    if not os.environ.get("QT_ENABLE_HIGHDPI_SCALING"):
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
