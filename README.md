# 🚗 AA Converter — APK to Android Auto

A powerful tool to patch any Android APK to declare Android Auto support. It decompiles the APK, injects the required manifest entries and resource files, rebuilds, and re-signs — all automatically.

## Features

- **One-click conversion** — Drop an APK, pick your Auto categories, and go
- **Video Player Support** — Built-in projection & distraction-optimized flags for YouTube, video streaming, and media players
- **Dual Install / Clone Mode** — Install alongside original app as a standalone application without asking to update or replace
- **App Name Customizer** — Easily rename the launcher title (e.g. "YouTube (Auto)")
- **App Icon Customizer** — Replace app icons with high-resolution custom images across all densities
- **Multiple Android Auto categories** — Media, Video, Messaging, Navigation, POI, IoT, Parking, Charging, Template
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
python aa_converter.py --input app.apk --categories media video template
```

## CLI Usage

```bash
python aa_converter.py [OPTIONS]

Options:
  --input, -i       Path to the input APK file (required)
  --output, -o      Path for the output APK (default: <name>_aa.apk)
  --categories, -c  Space-separated Auto categories (default: media video template)
                    Choices: media, video, notification, template, navigation, poi,
                             iot, parking, charging
  --clone           Clone APK to install as a standalone app alongside original
  --package-id      Custom package ID for cloned app (default: <package>.auto)
  --app-name        Custom display title / launcher name
  --icon            Path to custom app icon (.png, .jpg, .webp)
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

# Clone as separate app so it won't ask to update existing app
python aa_converter.py -i myapp.apk --clone --app-name "MyApp Auto"

# Full custom package with icon and name
python aa_converter.py -i myapp.apk --clone --app-name "My Music" --icon custom_icon.png

# Navigation app conversion
python aa_converter.py -i maps.apk -c navigation template -o maps_auto.apk
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

## 📺 Video Player & YouTube Setup for Android Auto

When converting video players or streaming apps (like YouTube ReVanced, VLC, Netflix, etc.):

1. **Keep "video" and "media" categories checked** (default):
   - Injects `distractionOptimized="true"` on the application and launcher activities.
   - Declares `android-automotive-video` library support.
   - Injects car projection categories (`CATEGORY_PROJECTION`, `CATEGORY_PROJECTION_OEM`, `CATEGORY_PROJECTION_CUSTOM`).
   - Automatically adds Android 14+ foreground media playback permissions (`FOREGROUND_SERVICE_MEDIA_PLAYBACK`, `WAKE_LOCK`, `MEDIA_CONTENT_CONTROL`).

2. **Enable Unknown Sources in Android Auto on your phone**:
   Because custom/converted video APKs are sideloaded (not from Google Play Store), Android Auto hides them by default unless "Unknown Sources" is enabled:
   - On your Android phone, go to **Settings** → **Apps** → **Android Auto** (or search "Android Auto" in Settings).
   - Scroll down to the bottom and tap **Version** repeatedly (10 times) until the prompt says *"Developer mode enabled"*.
   - Tap the **3 vertical dots (⋮)** in the top right corner → **Developer settings**.
   - Check the box for **"Unknown sources"**.
   - Under **Application Mode**, make sure **"Release"** or **"Developer"** is selected.
   - Plug your phone into your car or wireless adapter — the converted video player will now be visible in your car's launcher!

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `java` not found | Install JDK 8+ and add to PATH |
| apktool decode fails | Try `--no-res` flag or update apktool |
| Signature verification fails | Use `--no-sign` and sign manually |
| App does not appear on car screen | Enable **Unknown sources** in Android Auto developer settings (see guide above) |
| App crashes on Auto | The app needs actual Auto UI code — this tool patches manifest declarations |

> **⚠️ Important:** This tool patches the APK *manifest and resources* to declare Android Auto support. For the app to actually function on Android Auto, the app's code must implement proper Android Auto services (MediaBrowserService, MessagingService, CarAppService, etc.). This tool is ideal for apps that already have the code but are missing the manifest declarations, or for testing/development purposes.

## License

MIT — use freely, modify freely.
