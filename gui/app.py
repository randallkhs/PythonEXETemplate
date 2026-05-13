"""Desktop GUI for ACS-Images-to-Image-Converter."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from converter import ConversionOptions, collect_image_paths, convert_batch, format_choices


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ACS-Images-to-Image-Converter")
        self.minsize(760, 560)
        if sys.platform == "darwin":
            self.configure(background="systemWindowBackgroundColor")

        self.selected_paths: list[str] = []
        self.output_dir = tk.StringVar()
        self.target_format = tk.StringVar(value="png")
        self.use_dimensions = tk.BooleanVar(value=False)
        self.width_value = tk.StringVar()
        self.height_value = tk.StringVar()
        self.preserve_aspect = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="Listo.")
        self.progress_value = tk.DoubleVar(value=0.0)

        self._worker: threading.Thread | None = None
        self._progress_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self.after(120, self._poll_progress_queue)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if sys.platform == "darwin" and "aqua" in style.theme_names():
            style.theme_use("aqua")

        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        sources_frame = ttk.LabelFrame(container, text="Origen", padding=12)
        sources_frame.pack(fill=tk.BOTH, expand=True)

        button_row = ttk.Frame(sources_frame)
        button_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(button_row, text="Agregar imágenes", command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Agregar carpeta", command=self._add_folder).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_row, text="Quitar selección", command=self._remove_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_row, text="Limpiar lista", command=self._clear_list).pack(side=tk.LEFT, padx=(8, 0))

        list_container = ttk.Frame(sources_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        self.source_list = tk.Listbox(list_container, selectmode=tk.EXTENDED, height=12)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.source_list.yview)
        self.source_list.configure(yscrollcommand=scrollbar.set)
        self.source_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        options_frame = ttk.LabelFrame(container, text="Opciones", padding=12)
        options_frame.pack(fill=tk.X, pady=(12, 0))

        format_row = ttk.Frame(options_frame)
        format_row.pack(fill=tk.X)
        ttk.Label(format_row, text="Formato de salida").pack(side=tk.LEFT)
        format_labels = [label for label, _ in format_choices()]
        format_keys = [key for _, key in format_choices()]
        format_combo = ttk.Combobox(
            format_row,
            values=format_labels,
            state="readonly",
            width=12,
        )
        format_combo.pack(side=tk.LEFT, padx=(8, 0))
        format_combo.current(1)
        format_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.target_format.set(format_keys[format_combo.current()]),
        )
        self.target_format.set(format_keys[1])

        dimensions_row = ttk.Frame(options_frame)
        dimensions_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Checkbutton(
            dimensions_row,
            text="Definir dimensiones",
            variable=self.use_dimensions,
            command=self._toggle_dimensions,
        ).pack(side=tk.LEFT)
        ttk.Label(dimensions_row, text="Ancho").pack(side=tk.LEFT, padx=(16, 4))
        self.width_entry = ttk.Entry(dimensions_row, textvariable=self.width_value, width=8, state=tk.DISABLED)
        self.width_entry.pack(side=tk.LEFT)
        ttk.Label(dimensions_row, text="Alto").pack(side=tk.LEFT, padx=(12, 4))
        self.height_entry = ttk.Entry(dimensions_row, textvariable=self.height_value, width=8, state=tk.DISABLED)
        self.height_entry.pack(side=tk.LEFT)
        ttk.Checkbutton(
            dimensions_row,
            text="Mantener proporción",
            variable=self.preserve_aspect,
        ).pack(side=tk.LEFT, padx=(16, 0))

        output_row = ttk.Frame(options_frame)
        output_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(output_row, text="Carpeta de salida").pack(side=tk.LEFT)
        ttk.Entry(output_row, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Button(output_row, text="Elegir", command=self._choose_output_dir).pack(side=tk.LEFT)

        action_row = ttk.Frame(container)
        action_row.pack(fill=tk.X, pady=(12, 0))
        self.convert_button = ttk.Button(action_row, text="Convertir", command=self._start_conversion)
        self.convert_button.pack(side=tk.LEFT)
        ttk.Label(action_row, textvariable=self.status_text).pack(side=tk.LEFT, padx=(12, 0))

        progress_row = ttk.Frame(container)
        progress_row.pack(fill=tk.X, pady=(12, 0))
        self.progress_bar = ttk.Progressbar(progress_row, variable=self.progress_value, maximum=100)
        self.progress_bar.pack(fill=tk.X)

        log_frame = ttk.LabelFrame(container, text="Registro", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _toggle_dimensions(self) -> None:
        state = tk.NORMAL if self.use_dimensions.get() else tk.DISABLED
        self.width_entry.configure(state=state)
        self.height_entry.configure(state=state)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png *.webp *.heic *.heif *.svg"),
                ("Todos los archivos", "*.*"),
            ],
        )
        self._append_paths(paths)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Seleccionar carpeta")
        if folder:
            self._append_paths([folder])

    def _append_paths(self, paths: tuple[str, ...] | list[str]) -> None:
        for path in paths:
            if path and path not in self.selected_paths:
                self.selected_paths.append(path)
                self.source_list.insert(tk.END, path)

    def _remove_selected(self) -> None:
        selected = list(self.source_list.curselection())
        for index in reversed(selected):
            self.source_list.delete(index)
            del self.selected_paths[index]

    def _clear_list(self) -> None:
        self.source_list.delete(0, tk.END)
        self.selected_paths.clear()

    def _choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if folder:
            self.output_dir.set(folder)

    def _parse_dimension(self, value: str, label: str) -> int | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = int(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} debe ser un número entero.") from exc
        if parsed <= 0:
            raise ValueError(f"{label} debe ser mayor que cero.")
        return parsed

    def _start_conversion(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        sources = collect_image_paths(self.selected_paths)
        if not sources:
            messagebox.showwarning("Sin imágenes", "Agrega archivos o una carpeta con imágenes compatibles.")
            return

        output_dir = self.output_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("Sin destino", "Selecciona la carpeta donde se guardarán las imágenes convertidas.")
            return

        try:
            width = height = None
            if self.use_dimensions.get():
                width = self._parse_dimension(self.width_value.get(), "Ancho")
                height = self._parse_dimension(self.height_value.get(), "Alto")
                if width is None and height is None:
                    raise ValueError("Indica al menos ancho o alto cuando defines dimensiones.")
        except ValueError as exc:
            messagebox.showerror("Dimensiones inválidas", str(exc))
            return

        options = ConversionOptions(
            target_format=self.target_format.get(),
            output_dir=Path(output_dir).expanduser().resolve(),
            width=width,
            height=height,
            preserve_aspect_ratio=self.preserve_aspect.get(),
        )

        self.convert_button.configure(state=tk.DISABLED)
        self.progress_value.set(0.0)
        self.status_text.set("Preparando conversión...")
        self._set_log("")

        self._worker = threading.Thread(
            target=self._run_conversion,
            args=(sources, options),
            daemon=True,
        )
        self._worker.start()

    def _run_conversion(self, sources: list[Path], options: ConversionOptions) -> None:
        def progress(done: int, total: int, current_name: str) -> None:
            percent = 0.0 if total == 0 else (done / total) * 100.0
            self._progress_queue.put(("progress", (percent, done, total, current_name)))

        results = convert_batch(sources, options, progress=progress)
        self._progress_queue.put(("done", results))

    def _poll_progress_queue(self) -> None:
        try:
            while True:
                event, payload = self._progress_queue.get_nowait()
                if event == "progress":
                    percent, done, total, current_name = payload
                    self.progress_value.set(percent)
                    self.status_text.set(f"Procesando {done} de {total}: {current_name}")
                elif event == "done":
                    self._finish_conversion(payload)
        except queue.Empty:
            pass
        self.after(120, self._poll_progress_queue)

    def _finish_conversion(self, results: list) -> None:
        self.convert_button.configure(state=tk.NORMAL)
        self.progress_value.set(100.0)

        success_count = sum(1 for result in results if result.success)
        failure_count = len(results) - success_count
        self.status_text.set(f"Completado: {success_count} correctas, {failure_count} con error.")

        lines: list[str] = []
        for result in results:
            if result.success:
                lines.append(f"OK  {result.source.name} -> {result.destination}")
            else:
                lines.append(f"ERR {result.source.name}: {result.message}")
        self._set_log("\n".join(lines))

        if failure_count:
            messagebox.showwarning(
                "Conversión finalizada con errores",
                f"{success_count} imágenes convertidas correctamente y {failure_count} con error.",
            )
        else:
            messagebox.showinfo(
                "Conversión completada",
                f"Se convirtieron {success_count} imágenes correctamente.",
            )

    def _set_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, text)
        self.log_text.configure(state=tk.DISABLED)


def run() -> None:
    app = ConverterApp()
    app.mainloop()
