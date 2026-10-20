# Hasib X Post Assistant

A free local Windows desktop app that generates X post drafts using Ollama, learns tone from sample posts in a CSV, and shows a popup after a random interval. It does not publish to X; you review and copy each draft yourself.

## Features
- CSV sample posts (`text` column; `post` or `sample` also accepted)
- User topic + custom instructions + language selection
- Uses a local Ollama model, so generation does not require a paid AI API
- Random reminder interval, default 25–35 minutes
- Popup includes a Copy post button
- Keeps a local history to help avoid repetitive drafts
- No X login, password, browser automation, or API key needed

## Requirements
- Windows 10 or newer
- Python 3.10+ recommended
- Ollama installed
- Enough RAM/storage for the model. A small model is recommended for modest computers.

## Setup
1. Install Python if needed: https://www.python.org/downloads/windows/
2. Install Ollama: https://ollama.com/download/windows
3. Open Command Prompt or PowerShell and download a small model:
   ```powershell
   ollama pull llama3.2:3b
   ```
   If that model is too slow for your PC, try `ollama pull llama3.2:1b` and change the model field in the app to `llama3.2:1b`.
4. Extract this ZIP to a folder.
5. Edit `samples.csv` in Excel or Notepad. Keep the header `id,text`; place one example post per row.
6. Double-click `run.bat`.
7. Enter your topic and instructions. Click **Generate now** to test.
8. Click **Start reminders** to get a new draft after a random 25–35 minute interval.

## Important
- Ollama must be installed and running, and the selected model must be downloaded.
- Keep the app open for reminders to work. Sleep/hibernate stops the timer.
- Draft generation may take a while on CPU-only computers.
- The app does not post automatically. It only drafts and copies text; you manually paste it into X.
- Review facts, links, claims, and wording before publishing.
