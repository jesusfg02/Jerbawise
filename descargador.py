import re
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_RE_DOWNLOADED  = re.compile(r'Downloaded\s+"?(.+?)"?\s*$', re.IGNORECASE)
_RE_SKIPPING    = re.compile(r'Skipping\s+"?(.+?)"?\s*(?:\(|$)', re.IGNORECASE)
_RE_ERROR       = re.compile(r'(?:Failed to download|Error downloading|Could not download)\s+"?(.+?)"?\s*(?:\(|:|$)', re.IGNORECASE)

class DescargaWorker(QThread):
    terminado          = pyqtSignal(bool)
    cancion_descargada = pyqtSignal(str)
    cancion_saltada    = pyqtSignal(str)
    cancion_error      = pyqtSignal(str)

    def __init__(self, url, destino):
        super().__init__()
        self.url     = url
        self.destino = destino

    def run(self):
        try:
            proceso = subprocess.Popen(
                ["spotdl", "download", self.url, "--output", str(self.destino)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            buf = b""
            while True:
                byte = proceso.stdout.read(1)
                if not byte:
                    break
                if byte in (b"\n", b"\r"):
                    linea = _ANSI.sub("", buf.decode("utf-8", errors="replace")).strip()
                    buf = b""
                    if linea:
                        self._parsear(linea)
                else:
                    buf += byte
            proceso.wait()
            self.terminado.emit(proceso.returncode == 0)
        except Exception as e:
            self.terminado.emit(False)

    def _parsear(self, linea: str):
        m = _RE_DOWNLOADED.search(linea)
        if m:
            self.cancion_descargada.emit(m.group(1).strip())
            return
        
        m = _RE_SKIPPING.search(linea)
        if m:
            self.cancion_saltada.emit(m.group(1).strip())
            return
        
        m = _RE_ERROR.search(linea)
        if m:
            self.cancion_error.emit(m.group(1).strip())
            return