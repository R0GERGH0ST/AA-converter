"""
aa_converter_gui.py — Modern GUI for the Android Auto APK Converter.

Built with CustomTkinter for a polished dark-mode experience.
"""

import os
import sys
import threading
import logging
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    print("CustomTkinter not found. Installing…")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from aa_converter import AAConverter
from manifest_patcher import VALID_CATEGORIES
from tool_manager import ToolManager

logger = logging.getLogger("AAConverter.GUI")

# ── Theme ─────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Colour palette ────────────────────────────────────────────────────
BG_DARK = "#1a1a2e"
BG_CARD = "#16213e"
ACCENT = "#0f3460"
ACCENT_LIGHT = "#533483"
SUCCESS = "#2ecc71"
ERROR = "#e74c3c"
WARNING = "#f39c12"
TEXT = "#e0e0e0"
TEXT_DIM = "#8e8e8e"


class AAConverterGUI(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("🚗 AA Converter — APK to Android Auto")
        self.geometry("820x720")
        self.minsize(720, 620)
        self.configure(fg_color=BG_DARK)

        # State
        self.input_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.sign_var = ctk.BooleanVar(value=True)
        self.clone_var = ctk.BooleanVar(value=False)
        self.app_name_var = ctk.StringVar()
        self.package_id_var = ctk.StringVar()
        self.icon_path_var = ctk.StringVar()
        self.category_vars: dict[str, ctk.BooleanVar] = {}
        self.converting = False

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="🚗  Android Auto APK Converter",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            header,
            text="v1.0",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_DIM,
        ).pack(side="right", padx=20)

        # ── Scrollable main area ──────────────────────────────────────
        main = ctk.CTkScrollableFrame(self, fg_color=BG_DARK)
        main.pack(fill="both", expand=True, padx=16, pady=(12, 0))

        # ── File selection card ───────────────────────────────────────
        file_card = self._card(main, "📁  APK File Selection")

        # Input row
        inp_frame = ctk.CTkFrame(file_card, fg_color="transparent")
        inp_frame.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(inp_frame, text="Input APK:", width=90, anchor="w",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkEntry(inp_frame, textvariable=self.input_path,
                     placeholder_text="Select an APK file…",
                     height=36).pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(inp_frame, text="Browse", width=80, height=36,
                      command=self._browse_input,
                      fg_color=ACCENT_LIGHT).pack(side="right")

        # Output row
        out_frame = ctk.CTkFrame(file_card, fg_color="transparent")
        out_frame.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkLabel(out_frame, text="Output APK:", width=90, anchor="w",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkEntry(out_frame, textvariable=self.output_path,
                     placeholder_text="Auto-generated if empty",
                     height=36).pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(out_frame, text="Browse", width=80, height=36,
                      command=self._browse_output,
                      fg_color=ACCENT_LIGHT).pack(side="right")

        # ── Categories card ───────────────────────────────────────────
        cat_card = self._card(main, "🏷️  Android Auto Categories")

        cat_desc = ctk.CTkLabel(
            cat_card,
            text="Select which Android Auto capabilities to declare in the APK:",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_DIM,
        )
        cat_desc.pack(anchor="w", padx=12, pady=(0, 8))

        cat_grid = ctk.CTkFrame(cat_card, fg_color="transparent")
        cat_grid.pack(fill="x", padx=12, pady=(0, 12))

        for i, (key, desc) in enumerate(VALID_CATEGORIES.items()):
            var = ctk.BooleanVar(value=(key in ("media", "template")))
            self.category_vars[key] = var

            cb = ctk.CTkCheckBox(
                cat_grid,
                text=f"{key}",
                variable=var,
                font=ctk.CTkFont(size=13),
                hover_color=ACCENT_LIGHT,
                border_color=TEXT_DIM,
            )
            cb.grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 8), pady=3)

            lbl = ctk.CTkLabel(
                cat_grid,
                text=f"— {desc}",
                font=ctk.CTkFont(size=11),
                text_color=TEXT_DIM,
            )
            lbl.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 24), pady=3)

        # ── Clone & Customization card ────────────────────────────────
        clone_card = self._card(main, "📱  App Cloning & Customization (Dual Install)")

        clone_top = ctk.CTkFrame(clone_card, fg_color="transparent")
        clone_top.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkCheckBox(
            clone_top,
            text="Clone as separate app (install alongside original without replacing/updating)",
            variable=self.clone_var,
            command=self._on_clone_toggle,
            font=ctk.CTkFont(size=13, weight="bold"),
            hover_color=ACCENT_LIGHT,
            border_color=TEXT_DIM,
        ).pack(anchor="w")

        self.clone_subframe = ctk.CTkFrame(clone_card, fg_color="transparent")
        self.clone_subframe.pack(fill="x", padx=12, pady=(0, 12))

        # App Name row
        name_row = ctk.CTkFrame(self.clone_subframe, fg_color="transparent")
        name_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(name_row, text="App Name:", width=105, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(name_row, textvariable=self.app_name_var,
                     placeholder_text="e.g. YouTube (Auto) — overrides display title",
                     height=34).pack(side="left", fill="x", expand=True, padx=8)

        # Package ID row
        pkg_row = ctk.CTkFrame(self.clone_subframe, fg_color="transparent")
        pkg_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(pkg_row, text="Package ID:", width=105, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(pkg_row, textvariable=self.package_id_var,
                     placeholder_text="Auto-generated (<package>.auto) if empty",
                     height=34).pack(side="left", fill="x", expand=True, padx=8)

        # Custom Icon row
        icon_row = ctk.CTkFrame(self.clone_subframe, fg_color="transparent")
        icon_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(icon_row, text="Custom Icon:", width=105, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(icon_row, textvariable=self.icon_path_var,
                     placeholder_text="Select image file (.png, .jpg, .webp)…",
                     height=34).pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(icon_row, text="Browse", width=80, height=34,
                      command=self._browse_icon,
                      fg_color=ACCENT_LIGHT).pack(side="right")

        # ── Options card ──────────────────────────────────────────────
        opt_card = self._card(main, "⚙️  Options")

        opt_row = ctk.CTkFrame(opt_card, fg_color="transparent")
        opt_row.pack(fill="x", padx=12, pady=(0, 12))

        ctk.CTkCheckBox(
            opt_row,
            text="Sign APK after conversion",
            variable=self.sign_var,
            font=ctk.CTkFont(size=13),
            hover_color=ACCENT_LIGHT,
            border_color=TEXT_DIM,
        ).pack(side="left")

        ctk.CTkLabel(
            opt_row,
            text="(uses debug key by default)",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=12)

        # ── Progress area ─────────────────────────────────────────────
        prog_card = self._card(main, "📊  Progress")

        self.progress_bar = ctk.CTkProgressBar(prog_card, height=16,
                                                corner_radius=8,
                                                fg_color=BG_DARK,
                                                progress_color=ACCENT_LIGHT)
        self.progress_bar.pack(fill="x", padx=12, pady=(0, 4))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            prog_card, text="Ready", font=ctk.CTkFont(size=12),
            text_color=TEXT_DIM,
        )
        self.progress_label.pack(anchor="w", padx=12, pady=(0, 8))

        # Log text box
        self.log_box = ctk.CTkTextbox(
            prog_card, height=160, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG_DARK, text_color=TEXT, border_color=ACCENT,
            border_width=1, corner_radius=8,
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

        # ── Action buttons ────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color=BG_DARK, height=60)
        btn_frame.pack(fill="x", padx=16, pady=12)

        self.convert_btn = ctk.CTkButton(
            btn_frame,
            text="🚀  Convert APK",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=SUCCESS,
            hover_color="#27ae60",
            text_color="white",
            command=self._start_conversion,
        )
        self.convert_btn.pack(side="right", padx=(8, 0))

        self.setup_btn = ctk.CTkButton(
            btn_frame,
            text="🔧  Download Tools",
            height=44,
            font=ctk.CTkFont(size=13),
            fg_color=ACCENT,
            hover_color=ACCENT_LIGHT,
            command=self._download_tools,
        )
        self.setup_btn.pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame,
            text="Clear Log",
            height=44,
            font=ctk.CTkFont(size=13),
            fg_color="#555555",
            hover_color="#666666",
            command=self._clear_log,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _card(self, parent, title: str) -> ctk.CTkFrame:
        """Create a styled card frame with a title."""
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=ACCENT)
        card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).pack(anchor="w", padx=12, pady=(12, 8))

        return card

    def _append_log(self, text: str):
        """Thread-safe log append."""
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, value: float, label: str = ""):
        def _do():
            self.progress_bar.set(value)
            if label:
                self.progress_label.configure(text=label)
        self.after(0, _do)

    # ------------------------------------------------------------------
    # Browse buttons & Toggles
    # ------------------------------------------------------------------
    def _on_clone_toggle(self):
        inp = self.input_path.get().strip()
        if inp:
            base, ext = os.path.splitext(inp)
            suffix = "_clone_aa" if self.clone_var.get() else "_aa"
            self.output_path.set(f"{base}{suffix}{ext}")

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title="Select Custom App Icon",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.webp"),
                ("PNG Images", "*.png"),
                ("JPEG Images", "*.jpg;*.jpeg"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self.icon_path_var.set(path)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select Input APK",
            filetypes=[("APK Files", "*.apk"), ("All Files", "*.*")],
        )
        if path:
            self.input_path.set(path)
            # Auto-set output
            base, ext = os.path.splitext(path)
            suffix = "_clone_aa" if self.clone_var.get() else "_aa"
            self.output_path.set(f"{base}{suffix}{ext}")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Converted APK As",
            defaultextension=".apk",
            filetypes=[("APK Files", "*.apk"), ("All Files", "*.*")],
        )
        if path:
            self.output_path.set(path)

    # ------------------------------------------------------------------
    # Download Tools
    # ------------------------------------------------------------------
    def _download_tools(self):
        if self.converting:
            return
        self.converting = True
        self.setup_btn.configure(state="disabled")

        def _worker():
            try:
                self._append_log("🔧 Downloading required tools…")
                mgr = ToolManager()
                ok, msg = mgr.ensure_tools(
                    progress_callback=lambda v, l: self._set_progress(v, f"Downloading {l}")
                )
                self._append_log(f"  → {msg}")
                if ok:
                    self._set_progress(1.0, "Tools ready ✅")
                else:
                    self._set_progress(0.0, "Tool download failed ❌")
            finally:
                self.converting = False
                self.after(0, lambda: self.setup_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Start Conversion
    # ------------------------------------------------------------------
    def _start_conversion(self):
        if self.converting:
            return

        # Validate input
        inp = self.input_path.get().strip()
        if not inp:
            messagebox.showerror("Error", "Please select an input APK file.")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("Error", f"Input file not found:\n{inp}")
            return

        # Get selected categories
        categories = [k for k, v in self.category_vars.items() if v.get()]
        if not categories:
            messagebox.showerror("Error", "Please select at least one Android Auto category.")
            return

        out = self.output_path.get().strip() or None

        self.converting = True
        self.convert_btn.configure(state="disabled")
        self._clear_log()
        self._set_progress(0.0, "Starting…")

        def _worker():
            try:
                converter = AAConverter(
                    input_apk=inp,
                    output_apk=out,
                    categories=categories,
                    sign=self.sign_var.get(),
                    clone=self.clone_var.get(),
                    package_id=self.package_id_var.get().strip() or None,
                    app_name=self.app_name_var.get().strip() or None,
                    icon_path=self.icon_path_var.get().strip() or None,
                    progress_callback=self._set_progress,
                    log_callback=self._append_log,
                )

                result = converter.convert()

                if result["success"]:
                    self._append_log("")
                    self._append_log("═" * 50)
                    self._append_log("  ✅  CONVERSION SUCCESSFUL!")
                    self._append_log(f"  📦  Output: {result['output']}")
                    self._append_log("═" * 50)
                    self._set_progress(1.0, "Conversion complete ✅")
                    self.after(0, lambda: messagebox.showinfo(
                        "Success",
                        f"APK converted successfully!\n\nOutput: {result['output']}"
                    ))
                else:
                    self._append_log("")
                    self._append_log(f"  ❌  FAILED: {result['error']}")
                    self._set_progress(0.0, "Conversion failed ❌")
                    self.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"Conversion failed:\n{result['error']}"
                    ))
            except Exception as exc:
                self._append_log(f"  ❌  Error: {exc}")
                self._set_progress(0.0, "Error ❌")
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.converting = False
                self.after(0, lambda: self.convert_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()


# ======================================================================
# Main
# ======================================================================
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = AAConverterGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
