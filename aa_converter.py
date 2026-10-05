"""
aa_converter.py — Core APK-to-Android-Auto conversion engine and CLI.

Usage:
    python aa_converter.py --input app.apk --categories media template
"""

import os
import sys
import shutil
import tempfile
import argparse
import logging
import time

from tool_manager import ToolManager
from manifest_patcher import ManifestPatcher, VALID_CATEGORIES

logger = logging.getLogger("AAConverter")


class AAConverter:
    """
    Converts a regular APK to declare Android Auto support.

    Pipeline:
        1. Decompile APK with apktool
        2. Patch AndroidManifest.xml
        3. Add automotive_app_desc.xml
        4. Rebuild APK with apktool
        5. Sign APK with uber-apk-signer (or keytool + apksigner)
    """

    def __init__(
        self,
        input_apk: str,
        output_apk: str | None = None,
        categories: list[str] | None = None,
        min_sdk: int | None = None,
        sign: bool = True,
        clone: bool = False,
        package_id: str | None = None,
        app_name: str | None = None,
        icon_path: str | None = None,
        keystore: str | None = None,
        ks_pass: str = "android",
        key_alias: str = "androiddebugkey",
        key_pass: str = "android",
        tools_dir: str | None = None,
        work_dir: str | None = None,
        progress_callback=None,
        log_callback=None,
    ):
        # Input validation
        if not os.path.isfile(input_apk):
            raise FileNotFoundError(f"Input APK not found: {input_apk}")

        self.input_apk = os.path.abspath(input_apk)
        self.categories = categories or ["media", "video", "template"]
        self.min_sdk = min_sdk
        self.sign = sign
        self.clone = clone
        self.package_id = package_id
        self.app_name = app_name
        self.icon_path = icon_path
        self.keystore = keystore
        self.ks_pass = ks_pass
        self.key_alias = key_alias
        self.key_pass = key_pass
        self.progress_callback = progress_callback
        self.log_callback = log_callback

        # Output path
        if output_apk:
            self.output_apk = os.path.abspath(output_apk)
        else:
            base, ext = os.path.splitext(self.input_apk)
            suffix = "_clone_aa" if clone else "_aa"
            self.output_apk = f"{base}{suffix}{ext}"

        # Tool manager
        self.tool_mgr = ToolManager(tools_dir)

        # Work directory (temp by default)
        if work_dir:
            self.work_dir = work_dir
            self._temp_dir = None
        else:
            self._temp_dir = tempfile.mkdtemp(prefix="aa_converter_")
            self.work_dir = self._temp_dir

        self.decompiled_dir = os.path.join(self.work_dir, "decompiled")

    # ------------------------------------------------------------------
    # Logging & progress helpers
    # ------------------------------------------------------------------
    def _log(self, message: str, level: str = "info"):
        getattr(logger, level)(message)
        if self.log_callback:
            self.log_callback(message)

    def _progress(self, value: float, label: str = ""):
        if self.progress_callback:
            self.progress_callback(value, label)

    # ------------------------------------------------------------------
    # Main conversion pipeline
    # ------------------------------------------------------------------
    def convert(self) -> dict:
        """
        Run the full conversion pipeline.
        Returns a summary dict with details of all changes made.
        """
        result = {
            "success": False,
            "input": self.input_apk,
            "output": self.output_apk,
            "categories": self.categories,
            "steps": [],
            "error": None,
        }

        try:
            # Step 0: Ensure tools
            self._progress(0.0, "Checking tools…")
            self._log("Checking tools…")
            ok, msg = self.tool_mgr.ensure_tools(
                progress_callback=lambda v, l: self._progress(v * 0.1, f"Downloading {l}")
            )
            if not ok:
                result["error"] = msg
                self._log(f"Tool setup failed: {msg}", "error")
                return result
            result["steps"].append("tools_ready")
            self._log("All tools ready.")

            # Step 1: Decompile
            self._progress(0.1, "Decompiling APK…")
            self._log(f"Decompiling: {os.path.basename(self.input_apk)}")
            decompile_ok = self._decompile()
            if not decompile_ok:
                result["error"] = "Decompilation failed"
                return result
            result["steps"].append("decompiled")
            self._log("Decompilation complete.")

            # Step 2: Patch manifest
            self._progress(0.4, "Patching manifest…")
            self._log("Patching AndroidManifest.xml…")
            patcher = ManifestPatcher(
                self.decompiled_dir,
                categories=self.categories,
                clone_mode=self.clone,
                new_package_id=self.package_id,
                app_name=self.app_name,
                icon_path=self.icon_path,
            )
            patch_result = patcher.patch(self.min_sdk)
            result["patch_details"] = patch_result
            result["steps"].append("patched")
            self._log("Manifest patching complete.")

            # Step 3: Rebuild
            self._progress(0.6, "Rebuilding APK…")
            self._log("Rebuilding APK…")
            rebuild_ok = self._rebuild()
            if not rebuild_ok:
                result["error"] = "Rebuild failed"
                return result
            result["steps"].append("rebuilt")
            self._log("Rebuild complete.")

            # Step 4: Sign
            if self.sign:
                self._progress(0.8, "Signing APK…")
                self._log("Signing APK…")
                sign_ok = self._sign_apk()
                if not sign_ok:
                    result["error"] = "Signing failed"
                    return result
                result["steps"].append("signed")
                self._log("Signing complete.")
            else:
                self._log("Signing skipped (--no-sign).")

            self._progress(1.0, "Done!")
            self._log(f"[OK] Converted APK saved to: {self.output_apk}")
            result["success"] = True

        except Exception as exc:
            result["error"] = str(exc)
            self._log(f"Error: {exc}", "error")
            logger.exception("Conversion failed")

        finally:
            self._cleanup()

        return result

    # ------------------------------------------------------------------
    # Step 1: Decompile
    # ------------------------------------------------------------------
    def _decompile(self) -> bool:
        """Decompile the input APK using apktool."""
        if os.path.exists(self.decompiled_dir):
            shutil.rmtree(self.decompiled_dir)

        proc = self.tool_mgr.run_apktool(
            ["d", self.input_apk, "-o", self.decompiled_dir, "-f", "-s"],
            timeout=600,
        )

        if proc.returncode != 0:
            self._log(f"apktool decode failed:\n{proc.stderr}", "error")
            # Try without resources as fallback
            self._log("Retrying without resources (--no-res)…", "warning")
            proc = self.tool_mgr.run_apktool(
                ["d", self.input_apk, "-o", self.decompiled_dir, "-f", "--no-res"],
                timeout=600,
            )
            if proc.returncode != 0:
                self._log(f"apktool decode failed again:\n{proc.stderr}", "error")
                return False
        return True

    # ------------------------------------------------------------------
    # Step 3: Rebuild
    # ------------------------------------------------------------------
    def _rebuild(self) -> bool:
        """Rebuild the patched APK using apktool."""
        rebuilt_apk = os.path.join(self.work_dir, "rebuilt.apk")

        proc = self.tool_mgr.run_apktool(
            ["b", self.decompiled_dir, "-o", rebuilt_apk, "--use-aapt2"],
            timeout=600,
        )

        if proc.returncode != 0:
            self._log(f"apktool build failed with aapt2:\n{proc.stderr}", "warning")
            # Retry without --use-aapt2
            self._log("Retrying without --use-aapt2…", "warning")
            proc = self.tool_mgr.run_apktool(
                ["b", self.decompiled_dir, "-o", rebuilt_apk],
                timeout=600,
            )
            if proc.returncode != 0:
                self._log(f"apktool build failed:\n{proc.stderr}", "error")
                return False

        self._rebuilt_apk = rebuilt_apk
        return True

    # ------------------------------------------------------------------
    # Step 4: Sign
    # ------------------------------------------------------------------
    def _sign_apk(self) -> bool:
        """Sign and zipalign the rebuilt APK using uber-apk-signer."""
        rebuilt_apk = getattr(self, "_rebuilt_apk", None)
        if not rebuilt_apk or not os.path.isfile(rebuilt_apk):
            self._log("No rebuilt APK found to sign.", "error")
            return False

        # First copy rebuilt APK to the target destination
        os.makedirs(os.path.dirname(os.path.abspath(self.output_apk)), exist_ok=True)
        shutil.copy2(rebuilt_apk, self.output_apk)

        # Sign and zipalign in-place
        args = [
            "--apks", self.output_apk,
            "--allowResign",
            "--overwrite",
        ]

        if self.keystore and os.path.isfile(self.keystore):
            args += [
                "--ks", self.keystore,
                "--ksPass", self.ks_pass,
                "--ksAlias", self.key_alias,
                "--ksKeyPass", self.key_pass,
            ]

        proc = self.tool_mgr.run_signer(args, timeout=180)

        if proc.returncode != 0:
            self._log(f"Signing failed:\n{proc.stderr}", "warning")
            return False

        # Clean up unnecessary .idsig file generated by APK Signature Scheme v4
        idsig_file = f"{self.output_apk}.idsig"
        if os.path.isfile(idsig_file):
            try:
                os.remove(idsig_file)
            except Exception:
                pass

        self._log(f"Signed APK: {self.output_apk}")
        return True

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def _cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug("Cleaned up temp dir: %s", self._temp_dir)
            except Exception:
                logger.warning("Could not clean up temp dir: %s", self._temp_dir)


# ======================================================================
# CLI
# ======================================================================
def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aa_converter",
        description="AA Converter -- Convert any APK to support Android Auto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python aa_converter.py -i myapp.apk -c media notification
  python aa_converter.py -i maps.apk -c navigation template -o maps_auto.apk
  python aa_converter.py -i app.apk --keystore release.jks --ks-pass secret

Valid categories: %(categories)s
        """ % {"categories": ", ".join(VALID_CATEGORIES.keys())},
    )

    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to the input APK file",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output APK path (default: <name>_aa.apk)",
    )
    parser.add_argument(
        "--categories", "-c", nargs="+",
        default=["media", "video", "template"],
        choices=list(VALID_CATEGORIES.keys()),
        help="Android Auto categories to declare (default: media video template)",
    )
    parser.add_argument(
        "--min-sdk", type=int, default=None,
        help="Override minimum SDK version (default: keep original, min 23)",
    )
    parser.add_argument(
        "--no-sign", action="store_true",
        help="Skip signing the output APK",
    )
    parser.add_argument(
        "--keystore", default=None,
        help="Path to custom keystore for signing",
    )
    parser.add_argument(
        "--ks-pass", default="android",
        help="Keystore password (default: android)",
    )
    parser.add_argument(
        "--key-alias", default="androiddebugkey",
        help="Key alias (default: androiddebugkey)",
    )
    parser.add_argument(
        "--key-pass", default="android",
        help="Key password (default: android)",
    )
    parser.add_argument(
        "--clone", action="store_true",
        help="Clone APK as an independent app to install alongside original without replacing it",
    )
    parser.add_argument(
        "--package-id", default=None,
        help="Custom package ID / Application ID for cloned app (default: <package>.auto)",
    )
    parser.add_argument(
        "--app-name", default=None,
        help="Custom app display name (launcher title)",
    )
    parser.add_argument(
        "--icon", default=None,
        help="Path to custom app icon image (.png, .jpg, .webp)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )
    return parser


def cli_main():
    parser = build_cli_parser()
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print()
    print("[*] AA Converter -- APK to Android Auto")
    print("=" * 45)
    print()

    def cli_log(msg):
        print(f"  {msg}")

    def cli_progress(value, label=""):
        bar_len = 30
        filled = int(bar_len * value)
        bar = "#" * filled + "-" * (bar_len - filled)
        pct = int(value * 100)
        print(f"\r  [{bar}] {pct:3d}%  {label:<40s}", end="", flush=True)
        if value >= 1.0:
            print()

    converter = AAConverter(
        input_apk=args.input,
        output_apk=args.output,
        categories=args.categories,
        min_sdk=args.min_sdk,
        sign=not args.no_sign,
        clone=args.clone,
        package_id=args.package_id,
        app_name=args.app_name,
        icon_path=args.icon,
        keystore=args.keystore,
        ks_pass=args.ks_pass,
        key_alias=args.key_alias,
        key_pass=args.key_pass,
        progress_callback=cli_progress,
        log_callback=cli_log,
    )

    print(f"  Input:      {converter.input_apk}")
    print(f"  Output:     {converter.output_apk}")
    print(f"  Categories: {', '.join(converter.categories)}")
    print(f"  Signing:    {'Yes' if not args.no_sign else 'No'}")
    print(f"  Clone Mode: {'Yes' if args.clone else 'No'}")
    if args.app_name:
        print(f"  App Name:   {args.app_name}")
    if args.icon:
        print(f"  Custom Icon:{args.icon}")
    print()

    result = converter.convert()

    print()
    if result["success"]:
        print("  [OK] Conversion successful!")
        print(f"  [>>] Output: {result['output']}")
    else:
        print(f"  [FAIL] Conversion failed: {result['error']}")
        sys.exit(1)

    print()


if __name__ == "__main__":
    cli_main()
