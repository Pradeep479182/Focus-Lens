# FocusLens

FocusLens is a privacy-first desktop focus and wellness assistant. It combines
a React/Vite interface, a Tauri desktop shell, local SQLite storage, and a
Python/OpenCV/MediaPipe pipeline for deriving presence, screen-facing, and
posture signals.

## Project layout

```text
src/             React pages, components, services, and application state
src-tauri/       Tauri native shell, permissions, migrations, and packaging
cv/              Local Python capture and computer-vision pipeline
tests/           Frontend/service tests
cv/tests/        Computer-vision tests
Docs/            Product, architecture, design, and implementation plans
```

## Run and validate

```powershell
npm install
npm run dev
npm test
npm run build
```

For CV tests, install `cv/requirements.txt` in a Python environment and run:

```powershell
python -m pip install -r cv/requirements.txt
python -m pip install pytest
Set-Location cv
python -m pytest tests
```

For the Tauri desktop app, install Rust with rustup and the Microsoft C++ Build
Tools/Windows SDK. Check those prerequisites with `npx tauri info`, then run:

```powershell
python cv/models/download_model.py
python cv/models/download_pose_model.py
npm run tauri:dev
npm run tauri:build
```

The MediaPipe task models are downloaded locally and are not committed. Tauri
bundles the models that are present when packaging; both models are required to
start CV. The desktop runtime also requires a compatible system Python and the
packages in `cv/requirements.txt`. See [the Tauri setup and packaging notes](./src-tauri/README.md).

## Desktop privacy and camera flow

The React webview is the only webcam owner. While CV is running, it sends
downsized JPEG frames to the local Python process through a Tauri subprocess
pipe. Python processes each frame in memory and emits only derived activity
signals to the app. Frames are not persisted or sent to a network service.
The desktop app stores session history and preferences in native SQLite. The
Vite browser preview uses a separate SQLite database persisted in that browser's
IndexedDB; browser-preview data is not shared with the desktop app. CV camera
processing is available only in the Tauri desktop runtime.

## Product and architecture references

See the six project foundation documents under [`Docs/`](./Docs/) for the PRD,
technical requirements, app flow, UI/UX brief, database schema, and
implementation plan.
