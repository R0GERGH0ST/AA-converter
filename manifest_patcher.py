"""
manifest_patcher.py — Patches AndroidManifest.xml to add Android Auto support declarations.

This module handles all XML manipulation needed to make an APK declare
Android Auto compatibility, including:
  - Adding the car application meta-data
  - Creating automotive_app_desc.xml resource
  - Ensuring minimum SDK version
  - Adding required permissions and features
"""

import os
import re
import copy
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger("AAConverter.ManifestPatcher")

# Android XML namespace
ANDROID_NS = "http://schemas.android.com/apk/res/android"
NS_MAP = {"android": ANDROID_NS}

# Register the namespace so ET doesn't generate ns0: prefixes
ET.register_namespace("android", ANDROID_NS)

# Valid Android Auto categories
VALID_CATEGORIES = {
    "media":        "Media playback (music, podcasts, audiobooks)",
    "notification": "Messaging / notification (SMS, chat apps)",
    "template":     "Templated app (Cars App Library)",
    "navigation":   "Navigation / turn-by-turn directions",
    "poi":          "Points of interest (parking, charging, food)",
    "iot":          "IoT / smart-device control",
    "parking":      "Parking services",
    "charging":     "EV charging services",
}


def _android_attr(name: str) -> str:
    """Return the fully-qualified Android namespace attribute name."""
    return f"{{{ANDROID_NS}}}{name}"


class ManifestPatcher:
    """Patches a decoded APK's AndroidManifest.xml for Android Auto support."""

    def __init__(self, decompiled_dir: str, categories: list[str] | None = None):
        self.decompiled_dir = decompiled_dir
        self.manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
        self.categories = categories or ["media", "template"]
        self._validate_categories()

        if not os.path.isfile(self.manifest_path):
            raise FileNotFoundError(f"AndroidManifest.xml not found in {decompiled_dir}")

    def _validate_categories(self):
        invalid = [c for c in self.categories if c not in VALID_CATEGORIES]
        if invalid:
            raise ValueError(
                f"Invalid categories: {invalid}. "
                f"Valid options: {list(VALID_CATEGORIES.keys())}"
            )

    # ------------------------------------------------------------------
    # Main patching entry point
    # ------------------------------------------------------------------
    def patch(self, min_sdk: int | None = None) -> dict:
        """
        Apply all patches. Returns a summary dict of changes made.
        """
        changes = {
            "meta_data_added": False,
            "automotive_xml_created": False,
            "min_sdk_updated": False,
            "permissions_added": [],
            "features_added": [],
            "categories": self.categories,
        }

        # Parse manifest
        tree = ET.parse(self.manifest_path)
        root = tree.getroot()

        # 1. Add car application meta-data
        changes["meta_data_added"] = self._add_car_metadata(root)

        # 2. Create automotive_app_desc.xml
        changes["automotive_xml_created"] = self._create_automotive_desc()

        # 3. Ensure minSdkVersion >= 23
        changes["min_sdk_updated"] = self._ensure_min_sdk(root, min_sdk or 23)

        # 4. Add car-related permissions
        changes["permissions_added"] = self._add_permissions(root)

        # 5. Add car-related features
        changes["features_added"] = self._add_features(root)

        # Write back the manifest
        self._write_manifest(tree)

        logger.info("Manifest patching complete: %s", changes)
        return changes

    # ------------------------------------------------------------------
    # 1. Add com.google.android.gms.car.application meta-data
    # ------------------------------------------------------------------
    def _add_car_metadata(self, root: ET.Element) -> bool:
        """Add the Android Auto meta-data tag to the <application> element."""
        app_elem = root.find("application")
        if app_elem is None:
            logger.error("No <application> element found in manifest!")
            return False

        meta_name = _android_attr("name")
        meta_resource = _android_attr("resource")

        # Check if already present
        for meta in app_elem.findall("meta-data"):
            if meta.get(meta_name) == "com.google.android.gms.car.application":
                logger.info("Car application meta-data already exists.")
                # Update resource reference if needed
                meta.set(meta_resource, "@xml/automotive_app_desc")
                return False

        # Add the meta-data element
        meta_elem = ET.SubElement(app_elem, "meta-data")
        meta_elem.set(meta_name, "com.google.android.gms.car.application")
        meta_elem.set(meta_resource, "@xml/automotive_app_desc")
        logger.info("Added car application meta-data to manifest.")
        return True

    # ------------------------------------------------------------------
    # 2. Create res/xml/automotive_app_desc.xml
    # ------------------------------------------------------------------
    def _create_automotive_desc(self) -> bool:
        """Create the automotive_app_desc.xml resource file."""
        xml_dir = os.path.join(self.decompiled_dir, "res", "xml")
        os.makedirs(xml_dir, exist_ok=True)

        desc_path = os.path.join(xml_dir, "automotive_app_desc.xml")

        # Build the XML content
        lines = ['<?xml version="1.0" encoding="utf-8"?>']
        lines.append("<automotiveApp>")
        for category in self.categories:
            lines.append(f'    <uses name="{category}" />')
        lines.append("</automotiveApp>")

        content = "\n".join(lines) + "\n"

        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Created automotive_app_desc.xml with categories: %s", self.categories)
        return True

    # ------------------------------------------------------------------
    # 3. Ensure minSdkVersion
    # ------------------------------------------------------------------
    def _ensure_min_sdk(self, root: ET.Element, min_sdk: int) -> bool:
        """
        Ensure the minSdkVersion is at least *min_sdk*.
        For apktool-decoded APKs, the SDK info is typically managed in apktool.yml.
        We only raise the minSdkVersion if the current one is strictly less than min_sdk.
        We DO NOT inject <uses-sdk> into AndroidManifest.xml if apktool.yml manages it,
        because doing so can override a higher minSdkVersion (e.g. 28) and cause AAPT2
        errors like '<adaptive-icon> elements require a sdk version of at least 26'.
        """
        changed = False
        apktool_yml = os.path.join(self.decompiled_dir, "apktool.yml")

        # 1. Check existing minSdkVersion in apktool.yml
        current_yml_min = None
        if os.path.isfile(apktool_yml):
            current_yml_min = self._get_apktool_yml_min_sdk(apktool_yml)

        # 2. If uses-sdk was ALREADY in AndroidManifest.xml, inspect/update it
        uses_sdk = root.find("uses-sdk")
        if uses_sdk is not None:
            manifest_min = uses_sdk.get(_android_attr("minSdkVersion"))
            try:
                manifest_min_val = int(manifest_min)
                if manifest_min_val < min_sdk:
                    uses_sdk.set(_android_attr("minSdkVersion"), str(min_sdk))
                    changed = True
                    logger.info("Updated manifest minSdkVersion from %d to %d", manifest_min_val, min_sdk)
            except (ValueError, TypeError):
                pass
        elif current_yml_min is None:
            # Only if neither apktool.yml nor AndroidManifest.xml had minSdkVersion, add it to manifest
            uses_sdk = ET.SubElement(root, "uses-sdk")
            uses_sdk.set(_android_attr("minSdkVersion"), str(min_sdk))
            changed = True
            logger.info("Added default minSdkVersion %d to manifest", min_sdk)

        # 3. Patch apktool.yml if present and current min < min_sdk
        if os.path.isfile(apktool_yml):
            if self._patch_apktool_yml_min_sdk(apktool_yml, min_sdk):
                changed = True

        return changed

    @staticmethod
    def _get_apktool_yml_min_sdk(yml_path: str) -> int | None:
        """Read the current minSdkVersion from apktool.yml."""
        try:
            with open(yml_path, "r", encoding="utf-8") as f:
                content = f.read()
            pattern = r"minSdkVersion:\s*['\"]?(\d+)['\"]?"
            match = re.search(pattern, content)
            if match:
                return int(match.group(1))
        except Exception as exc:
            logger.warning("Could not parse minSdkVersion from apktool.yml: %s", exc)
        return None

    @staticmethod
    def _patch_apktool_yml_min_sdk(yml_path: str, min_sdk: int) -> bool:
        """Patch minSdkVersion in apktool.yml only if it is less than min_sdk."""
        try:
            with open(yml_path, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = r"(minSdkVersion:\s*['\"]?)(\d+)(['\"]?)"
            match = re.search(pattern, content)
            if match:
                current = int(match.group(2))
                if current < min_sdk:
                    content = re.sub(
                        pattern,
                        lambda m: f"{m.group(1)}{min_sdk}{m.group(3)}",
                        content,
                    )
                    with open(yml_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info("Patched apktool.yml minSdkVersion from %d to %d", current, min_sdk)
                    return True
                else:
                    logger.info("Existing apktool.yml minSdkVersion is %d (>= required %d), keeping it.", current, min_sdk)
        except Exception as exc:
            logger.warning("Could not patch apktool.yml: %s", exc)
        return False

    # ------------------------------------------------------------------
    # 4. Add required permissions
    # ------------------------------------------------------------------
    def _add_permissions(self, root: ET.Element) -> list[str]:
        """Add Android Auto related permissions if not already present."""
        permissions_to_add = []

        # Core permissions for media apps
        if "media" in self.categories:
            permissions_to_add.append("android.permission.FOREGROUND_SERVICE")
            permissions_to_add.append("android.permission.MEDIA_CONTENT_CONTROL")

        # Messaging permissions
        if "notification" in self.categories:
            permissions_to_add.append("android.permission.READ_CONTACTS")

        # Navigation
        if "navigation" in self.categories:
            permissions_to_add.append("android.permission.ACCESS_FINE_LOCATION")
            permissions_to_add.append("android.permission.ACCESS_COARSE_LOCATION")
            permissions_to_add.append("android.permission.FOREGROUND_SERVICE")

        # Get existing permissions
        existing = set()
        for perm in root.findall("uses-permission"):
            name = perm.get(_android_attr("name"), "")
            existing.add(name)

        added = []
        for perm_name in permissions_to_add:
            if perm_name not in existing:
                perm_elem = ET.SubElement(root, "uses-permission")
                perm_elem.set(_android_attr("name"), perm_name)
                added.append(perm_name)
                existing.add(perm_name)

        if added:
            logger.info("Added permissions: %s", added)
        return added

    # ------------------------------------------------------------------
    # 5. Add uses-feature declarations
    # ------------------------------------------------------------------
    def _add_features(self, root: ET.Element) -> list[str]:
        """Add Android Auto feature declarations."""
        features_to_add = [
            ("android.hardware.type.automotive", "false"),
        ]

        if "navigation" in self.categories:
            features_to_add.append(("android.hardware.location.gps", "false"))

        # Get existing features
        existing = set()
        for feat in root.findall("uses-feature"):
            name = feat.get(_android_attr("name"), "")
            existing.add(name)

        added = []
        for feat_name, required in features_to_add:
            if feat_name not in existing:
                feat_elem = ET.SubElement(root, "uses-feature")
                feat_elem.set(_android_attr("name"), feat_name)
                feat_elem.set(_android_attr("required"), required)
                added.append(feat_name)

        if added:
            logger.info("Added features: %s", added)
        return added

    # ------------------------------------------------------------------
    # Write manifest back
    # ------------------------------------------------------------------
    def _write_manifest(self, tree: ET.ElementTree):
        """Write the modified manifest XML back to disk."""
        # ET doesn't write the XML declaration by default; we add it manually
        tree.write(
            self.manifest_path,
            encoding="utf-8",
            xml_declaration=True,
        )
        logger.info("Wrote patched manifest to %s", self.manifest_path)
