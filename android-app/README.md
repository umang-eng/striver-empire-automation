# Striver Empire Automation — Native Android App

Native Kotlin + Jetpack Compose Android application (`minSdk 26`, `targetSdk 35`) that runs the full Striver Empire automation **directly on-device** with zero external backend server latency.

## Features
- **Apple Liquid Glass UI**: Full-screen looping muted non-pausable/non-selectable/non-downloadable background video (`res/raw/background.mp4`), frosted light-glass black-bold header, translucent central `<Category> <Discount>%` input, searchable/tabbed Category Suggestions panel (click-to-insert & copy-to-clipboard), live 11-stage progress screen, and completion cards.
- **Direct On-Device Extraction**: Connects directly to `https://striverempire.com/` via `OkHttp` (Laravel cookie/XSRF session) + `Jsoup`, resolves main categories and ordered subcategories, paginates `filter-products`, visits every product page, detects sizes (`NA` fallback), and calculates `Real Price` using `BigDecimal` (`HALF_UP`).
- **Native Excel & Single-Page PDF Generation**: Generates `<Category> <Discount>%.xlsx` (OpenXML ZIP) and 1-page landscape `<Category> <Discount>%.pdf` (`PdfDocument`) with randomized high-contrast header colors, comma-free `0.00` prices, and Save-to-Downloads / Open / Share actions.

## Build & Install APK

```bash
cd /Users/umang/Music/Striver-Empire-automation/android-app
./gradlew testDebugUnitTest assembleDebug
```

The debug APK is generated at:
`android-app/app/build/outputs/apk/debug/app-debug.apk`

Install onto a connected Android device or emulator:
```bash
~/Library/Android/sdk/platform-tools/adb install -r app/build/outputs/apk/debug/app-debug.apk
```
