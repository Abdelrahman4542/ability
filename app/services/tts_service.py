"""Text-to-speech with a reliable Windows System.Speech backend.

On Windows the built-in .NET speech synthesizer is preferred because it does not
depend on pyttsx3's COM event loop. Other platforms use pyttsx3.
"""
import base64
import os
import queue
import shutil
import subprocess
import threading

from PySide6.QtCore import QObject, Signal


class TTSService(QObject):
    status_changed = Signal(str)

    def __init__(self, rate=155, volume=1.0):
        super().__init__()
        self.rate = int(rate)
        self.volume = max(0.0, min(1.0, float(volume)))
        self._queue = queue.Queue()
        self._process = None
        self._process_lock = threading.Lock()
        self._cancelled_process_ids = set()
        self.available = None
        self.error = None
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="AbilityBridge-TTS"
        )
        self._thread.start()

    @staticmethod
    def _powershell_path():
        return shutil.which("powershell.exe") or shutil.which("powershell")

    def _windows_speak(self, text):
        encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
        volume = int(round(self.volume * 100))
        # System.Speech uses a relative -10..10 rate, not words per minute.
        speech_rate = max(-10, min(10, int(round((self.rate - 155) / 18))))
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Volume = {volume}
$synth.Rate = {speech_rate}
$voices = $synth.GetInstalledVoices()
$voicePreference = 'arabic'
try {{
    $reg = Get-ItemProperty -Path 'HKCU:\\Software\\AbilityBridge\\AbilityBridgeAI' -ErrorAction SilentlyContinue
    if ($null -ne $reg -and $reg.tts_voice) {{ $voicePreference = [string]$reg.tts_voice }}
}} catch {{}}
if ($voicePreference -eq 'arabic') {{
    $arVoice = $voices | Where-Object {{
        $_.VoiceInfo.Culture.Name -like 'ar*' -or $_.VoiceInfo.Name -match 'Arabic|Hoda|Naayf'
    }} | Select-Object -First 1
    if ($null -ne $arVoice) {{
        $synth.SelectVoice($arVoice.VoiceInfo.Name)
        Write-Output ('ABILITYBRIDGE_VOICE=' + $arVoice.VoiceInfo.Name)
    }} else {{
        Write-Output ('ABILITYBRIDGE_VOICE=' + $synth.Voice.Name)
        Write-Output 'ABILITYBRIDGE_WARNING=No Arabic voice is installed; using the default Windows voice.'
    }}
}} else {{
    Write-Output ('ABILITYBRIDGE_VOICE=' + $synth.Voice.Name)
}}
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_text}'))
$synth.Speak($text)
$synth.Dispose()
"""
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        executable = self._powershell_path()
        if not executable:
            raise RuntimeError("Windows PowerShell was not found.")
        process = subprocess.Popen(
            [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", encoded_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._process_lock:
            self._process = process
        stdout, stderr = process.communicate()
        with self._process_lock:
            if self._process is process:
                self._process = None
            was_cancelled = process.pid in self._cancelled_process_ids
            self._cancelled_process_ids.discard(process.pid)
        if was_cancelled:
            return "Speech stopped."
        if process.returncode != 0:
            detail = (stderr or stdout or "System.Speech returned an unknown error").strip()
            raise RuntimeError(detail[-1200:])
        warning = next(
            (line.split("=", 1)[1] for line in stdout.splitlines()
             if line.startswith("ABILITYBRIDGE_WARNING=")),
            None,
        )
        voice = next(
            (line.split("=", 1)[1] for line in stdout.splitlines()
             if line.startswith("ABILITYBRIDGE_VOICE=")),
            "Windows speech voice",
        )
        return warning or f"Finished speaking with {voice}."

    def _worker(self):
        if os.name == "nt" and self._powershell_path():
            self.available = True
            self.status_changed.emit(
                "Windows speech service ready. Arabic pronunciation requires an Arabic Windows voice."
            )
            while True:
                item = self._queue.get()
                if item is None:
                    break
                if item == "__STOP__":
                    continue
                try:
                    message = self._windows_speak(item)
                    self.status_changed.emit(message)
                except Exception as exc:
                    self.error = f"{type(exc).__name__}: {exc}"
                    self.available = False
                    self.status_changed.emit(f"Speech failed: {self.error}")
            return

        # Cross-platform fallback.
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            voices = engine.getProperty("voices") or []
            for voice in voices:
                desc = f"{getattr(voice, 'id', '')} {getattr(voice, 'name', '')}".lower()
                if any(key in desc for key in ("arab", "ar-", "ar_", "hoda", "naayf")):
                    engine.setProperty("voice", voice.id)
                    break
            self.available = True
            self.status_changed.emit("Speech engine ready.")
        except Exception as exc:
            self.available = False
            self.error = f"{type(exc).__name__}: {exc}"
            self.status_changed.emit(f"Speech engine unavailable: {self.error}")

        while True:
            item = self._queue.get()
            if item is None:
                break
            if item == "__STOP__":
                if engine is not None:
                    try:
                        engine.stop()
                    except Exception:
                        pass
                continue
            if engine is None:
                self.status_changed.emit(f"Cannot speak: {self.error or 'speech engine unavailable'}")
                continue
            try:
                engine.say(item)
                engine.runAndWait()
                self.status_changed.emit("Finished speaking.")
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self.status_changed.emit(f"Speech failed: {self.error}")
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    def speak(self, text):
        value = str(text).strip()
        if not value:
            self.status_changed.emit("There is no text to read.")
            return False
        self.stop()
        self._queue.put(value)
        self.status_changed.emit("Preparing speech…")
        return True

    def stop(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            try:
                with self._process_lock:
                    self._cancelled_process_ids.add(process.pid)
                process.terminate()
            except Exception:
                pass
        self._queue.put("__STOP__")

    def close(self):
        self.stop()
        self._queue.put(None)
