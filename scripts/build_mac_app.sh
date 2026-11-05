#!/bin/zsh
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"

# The installed command-line compiler is newer than the default SDK on this Mac.
# The 15.4 SDK is compatible with it and still supports our macOS 14 target.
sdk_path="/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk"
if [[ ! -d "$sdk_path" ]]; then
  sdk_path="$(xcrun --show-sdk-path)"
fi
export SDKROOT="$sdk_path"
export CLANG_MODULE_CACHE_PATH="$project_root/.build/clang-cache"
export SWIFTPM_MODULECACHE_OVERRIDE="$project_root/.build/swiftpm-cache"

swift build --sdk "$sdk_path"

app_path="$project_root/dist/EditLock.app"
mkdir -p "$app_path/Contents/MacOS"
cp "$project_root/.build/debug/EditLockMac" "$app_path/Contents/MacOS/EditLockMac"
cat > "$app_path/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleExecutable</key><string>EditLockMac</string>
  <key>CFBundleIdentifier</key><string>com.abhinav.editlock</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>EditLock</string>
  <key>CFBundleDisplayName</key><string>EditLock</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

codesign --force --sign - "$app_path"
echo "Built $app_path"
