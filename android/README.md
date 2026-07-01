# AXIOMN Mobile (Android MVP)

"Zero choice" push-to-talk client for the AXIOMN backend: hold the mic
button, speak, release — AXIOMN classifies your request, routes it, and
speaks the answer back. One screen, one button, no settings beyond the
server address.

## What this is (and isn't)

This is a **push-to-talk** MVP, not an always-listening "Siri replacement":

- ✅ Tap-and-hold mic button → on-device speech recognition (`SpeechRecognizer`)
  → `POST /intent` to the AXIOMN backend → spoken reply (`TextToSpeech`) →
  a routing-transparency panel (intent, route, tool, confidence, execution
  time), same idea as the web demo at `/ui/`.
- ❌ No wake word, no background/foreground service, no on-device
  automation (Accessibility Service). Those need real-device testing —
  battery-exemption prompts, always-on mic UX, permission edge cases —
  that can't be verified in a sandboxed environment with no Android
  emulator. Building that blind and calling it done would be worse than
  not building it.

**Build status: unverified.** This environment has Gradle but no Android
SDK (`ANDROID_HOME` unset, no `adb`/`sdkmanager`) and no network path to
`services.gradle.org` to fetch a Gradle distribution, so the project has
never actually been compiled or run here. What *was* checked:
all four XML resource files parse as well-formed XML, and every `R.id` /
`R.string` / theme reference in the Kotlin code matches a declared
resource (checked by grep, not by the Android resource compiler). Treat
this as a real starting point to open in Android Studio, not as a
verified build.

## Structure

```
android/
├── app/
│   ├── build.gradle.kts          # AGP 8.2.2, Kotlin 1.9.22, compileSdk 34, minSdk 26
│   └── src/main/
│       ├── AndroidManifest.xml   # RECORD_AUDIO + INTERNET permissions
│       ├── java/com/axiomn/assistant/
│       │   ├── MainActivity.kt       # push-to-talk flow, permission handling, TTS
│       │   └── AxiomnApiClient.kt    # HttpURLConnection client for POST /intent
│       └── res/                  # layout, strings, theme
├── build.gradle.kts
├── settings.gradle.kts
└── gradle/wrapper/gradle-wrapper.properties   # wrapper *jar* not included (see below)
```

## Opening it

1. Open the `android/` directory in Android Studio (Hedgehog or newer).
   Android Studio will offer to generate the missing `gradlew` /
   `gradlew.bat` / `gradle-wrapper.jar` on sync — accept it, since this
   repo only ships `gradle-wrapper.properties` (the binary wrapper jar
   couldn't be fetched in this sandbox).
2. Run the `app` configuration on an emulator or device with Google Play
   Services (needed for on-device speech recognition) and a microphone.
3. Run the AXIOMN backend from the repo root (`uvicorn axiomn.api.main:app`)
   and set the server URL field in the app:
   - Emulator: `http://10.0.2.2:8000` (default, maps to the host machine)
   - Physical device on the same network: `http://<your-machine-LAN-IP>:8000`

## Talking to the backend

`AxiomnApiClient.kt` mirrors the API response shape from
`axiomn/api/main.py` exactly (`intent`, `topic`, `language`, `difficulty`,
`confidence`, `route`, `tool`, `result`, `execution_time_ms`) — if that
schema changes, this file needs updating too.
