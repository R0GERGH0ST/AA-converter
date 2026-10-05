"""
tool_manager.py — Downloads and manages external tools (apktool, uber-apk-signer).
"""

import os
import sys
import shutil
import subprocess
import logging
import requests

logger = logging.getLogger("AAConverter.ToolManager")

# Tool download URLs
APKTOOL_VERSION = "2.10.0"
APKTOOL_URL = f"https://github.com/iBotPeaches/Apktool/releases/download/v{APKTOOL_VERSION}/apktool_{APKTOOL_VERSION}.jar"

UBER_SIGNER_VERSION = "1.3.0"
UBER_SIGNER_URL = f"https://github.com/patrickfav/uber-apk-signer/releases/download/v{UBER_SIGNER_VERSION}/uber-apk-signer-{UBER_SIGNER_VERSION}.jar"

# Fallback signer URL
UBER_SIGNER_FALLBACK_URL = "https://github.com/patrickfav/uber-apk-signer/releases/latest/download/uber-apk-signer.jar"


class ToolManager:
    """Manages external tool dependencies required for APK manipulation."""

    def __init__(self, tools_dir: str | None = None):
        if tools_dir is None:
            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
        self.tools_dir = tools_dir
        os.makedirs(self.tools_dir, exist_ok=True)

        self.apktool_jar = os.path.join(self.tools_dir, "apktool.jar")
        self.signer_jar = os.path.join(self.tools_dir, "uber-apk-signer.jar")

    # ------------------------------------------------------------------
    # Java check
    # ------------------------------------------------------------------
    @staticmethod
    def check_java() -> bool:
        """Return True if Java is available on the system PATH."""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            version_line = result.stderr.strip().split("\n")[0] if result.stderr else ""
            logger.info("Java found: %s", version_line)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------
    # Download helper
    # ------------------------------------------------------------------
    def _download_file(self, url: str, dest: str, label: str = "",
                       progress_callback=None) -> bool:
        """Download a file from *url* to *dest*. Returns True on success."""
        label = label or os.path.basename(dest)
        logger.info("Downloading %s from %s …", label, url)
        try:
            resp = requests.get(url, stream=True, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded / total, label)
            logger.info("Downloaded %s (%s bytes)", label, downloaded)
            return True
        except Exception as exc:
            logger.error("Failed to download %s: %s", label, exc)
            if os.path.exists(dest):
                os.remove(dest)
            return False

    # ------------------------------------------------------------------
    # Tool availability checks
    # ------------------------------------------------------------------
    def has_apktool(self) -> bool:
        return os.path.isfile(self.apktool_jar)

    def has_signer(self) -> bool:
        return os.path.isfile(self.signer_jar)

    def all_tools_ready(self) -> bool:
        return self.has_apktool() and self.has_signer() and self.check_java()

    # ------------------------------------------------------------------
    # Download tools
    # ------------------------------------------------------------------
    def download_apktool(self, progress_callback=None) -> bool:
        if self.has_apktool():
            logger.info("apktool.jar already present.")
            return True
        return self._download_file(APKTOOL_URL, self.apktool_jar,
                                   f"apktool {APKTOOL_VERSION}", progress_callback)

    def download_signer(self, progress_callback=None) -> bool:
        if self.has_signer():
            logger.info("uber-apk-signer.jar already present.")
            return True
        ok = self._download_file(UBER_SIGNER_URL, self.signer_jar,
                                 f"uber-apk-signer {UBER_SIGNER_VERSION}",
                                 progress_callback)
        if not ok:
            logger.info("Trying fallback signer URL …")
            ok = self._download_file(UBER_SIGNER_FALLBACK_URL, self.signer_jar,
                                     "uber-apk-signer (fallback)", progress_callback)
        return ok

    def ensure_tools(self, progress_callback=None) -> tuple[bool, str]:
        """Download all required tools. Returns (success, message)."""
        if not self.check_java():
            return False, ("Java is not installed or not on PATH. "
                           "Please install JDK 8+ and try again.")

        msgs = []
        if not self.download_apktool(progress_callback):
            msgs.append("Failed to download apktool.")
        if not self.download_signer(progress_callback):
            msgs.append("Failed to download uber-apk-signer.")

        if msgs:
            return False, " ".join(msgs)
        return True, "All tools ready."

    # ------------------------------------------------------------------
    # Run external tools
    # ------------------------------------------------------------------
    def run_apktool(self, args: list[str], cwd: str | None = None,
                    timeout: int = 300) -> subprocess.CompletedProcess:
        """Run apktool with the given arguments."""
        cmd = ["java", "-jar", self.apktool_jar] + args
        logger.info("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )

    def run_signer(self, args: list[str], cwd: str | None = None,
                   timeout: int = 120) -> subprocess.CompletedProcess:
        """Run uber-apk-signer with the given arguments."""
        cmd = ["java", "-jar", self.signer_jar] + args
        logger.info("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
