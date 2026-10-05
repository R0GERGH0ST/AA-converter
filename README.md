# 🚗 AA Converter — APK to Android Auto

A powerful tool to patch any Android APK to declare Android Auto support. It decompiles the APK, injects the required manifest entries and resource files, rebuilds, and re-signs — all automatically.

## Features

- **One-click conversion** — Drop an APK, pick your Auto categories, and go
- **Multiple Android Auto categories** — Media, Messaging, Navigation, POI, IoT, Parking, Charging, Template
- **Modern GUI** — Beautiful dark-mode interface built with CustomTkinter
- **CLI mode** — Scriptable for CI/CD and batch processing
- **Auto-downloads tools** — Fetches `apktool.jar` and `uber-apk-signer.jar` on first run
- **Smart manifest patching** — Non-destructive XML manipulation preserving existing attributes
- **Debug & release signing** — Auto-generates a debug keystore or use your own

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.8+ |
| Java | 8+ (JDK or JRE) |

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Launch the GUI
python aa_converter_gui.py

# 3. Or use the CLI
python aa_converter.py --input app.apk --categories media notification
```

## CLI Usage

```bash
python aa_converter.py [OPTIONS]

Options:
  --input, -i       Path to the input APK file (required)
  --output, -o      Path for the output APK (default: <name>_aa.apk)
  --categories, -c  Space-separated Auto categories (default: media template)
                    Choices: media, notification, template, navigation, poi,
                             iot, parking, charging
  --min-sdk         Override minimum SDK version (default: keep original)
  --no-sign         Skip signing the output APK
  --keystore        Path to custom keystore for signing
  --ks-pass         Keystore password (default: android)
  --key-alias       Key alias (default: androiddebugkey)
  --key-pass        Key password (default: android)
  --verbose, -v     Enable verbose logging
```

### Examples

```bash
# Convert with media + notification support
python aa_converter.py -i myapp.apk -c media notification

# Navigation app conversion
python aa_converter.py -i maps.apk -c navigation template -o maps_auto.apk

# Using a custom keystore
python aa_converter.py -i app.apk --keystore release.jks --ks-pass mypass
```

## How It Works

1. **Decompile** — Uses `apktool` to decode the APK into readable XML + smali
2. **Patch Manifest** — Injects `com.google.android.gms.car.application` meta-data
3. **Add Resources** — Creates `res/xml/automotive_app_desc.xml` with chosen categories
4. **Ensure minSdk** — Ensures `minSdkVersion` is at least 23 (Android Auto requirement)
5. **Rebuild** — Recompiles the patched project back into an APK
6. **Align & Sign** — Zipaligns and signs with debug or custom keystore

## Project Structure

```
AA converter/
├── aa_converter.py          # Core conversion engine + CLI
├── aa_converter_gui.py      # CustomTkinter GUI
├── manifest_patcher.py      # AndroidManifest.xml manipulation
├── tool_manager.py          # Downloads & manages apktool/signer
├── requirements.txt         # Python dependencies
├── tools/                   # Auto-downloaded JARs (created at runtime)
└── README.md
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `java` not found | Install JDK 8+ and add to PATH |
| apktool decode fails | Try `--no-res` flag or update apktool |
| Signature verification fails | Use `--no-sign` and sign manually |
| App crashes on Auto | The app needs actual Auto UI code — this tool only patches the manifest |

> **⚠️ Important:** This tool patches the APK *manifest and resources* to declare Android Auto support. For the app to actually function on Android Auto, the app's code must implement proper Android Auto services (MediaBrowserService, MessagingService, CarAppService, etc.). This tool is ideal for apps that already have the code but are missing the manifest declarations, or for testing/development purposes.

## License

MIT — use freely, modify freely.
