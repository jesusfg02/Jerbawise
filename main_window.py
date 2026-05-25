import sys
import os
import ctypes
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QProgressBar, QFileDialog, QDialog
)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QColor, QIcon

from biblioteca import escanear_biblioteca
from descargador import DescargaWorker

# ── RUTAS SEGURAS DEL SISTEMA ──
# Localiza la carpeta AppData de Windows de forma automática
directorio_appdata = Path(os.getenv('APPDATA', str(Path.home()))) / "Jerbawise_App"
directorio_appdata.mkdir(parents=True, exist_ok=True) # Crea la carpeta si no existe
CONFIG_FILE = directorio_appdata / "config.json"

def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if "ruta_musica" in data:
                    return Path(data["ruta_musica"])
            except:
                pass
    return None

def guardar_config(ruta):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"ruta_musica": str(ruta)}, f)

def obtener_ruta(ruta_relativa):
    try:
        ruta_base = sys._MEIPASS
    except Exception:
        ruta_base = os.path.abspath(".")
    return os.path.join(ruta_base, ruta_relativa)


class DialogoBienvenida(QDialog):
    def __init__(self, ruta_defecto, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración Inicial — Jerbawise")
        self.setFixedSize(500, 160)
        self.ruta_elegida = ruta_defecto
        
        # ── Forzar el fondo negro puro ──
        self.setStyleSheet("QDialog { background-color: #000000; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Texto explicativo
        lbl_info = QLabel("¡Bienvenido! Selecciona la carpeta donde se guardará tu música:")
        lbl_info.setStyleSheet("font-size: 12px; color: #FFFFFF; font-weight: bold;")
        layout.addWidget(lbl_info)

        # Componentes de ruta (Caja de texto + Botón Examinar)
        lay_ruta = QHBoxLayout()
        self.input_ruta = QLineEdit(str(self.ruta_elegida))
        self.input_ruta.setReadOnly(True)
        self.input_ruta.setFixedHeight(32)
        self.input_ruta.setStyleSheet("""
            QLineEdit { 
                background-color: #111111; 
                color: #A0A0A0; 
                border: 1px solid #222222; 
                padding-left: 8px; 
                font-size: 11px;
            }
        """)
        
        btn_examinar = QPushButton("Examinar...")
        btn_examinar.setFixedHeight(32)
        btn_examinar.setFixedWidth(100)
        btn_examinar.clicked.connect(self._abrir_explorador)

        lay_ruta.addWidget(self.input_ruta)
        lay_ruta.addWidget(btn_examinar)
        layout.addLayout(lay_ruta)

        layout.addSpacing(5)

        # Botón Aceptar para confirmar
        btn_aceptar = QPushButton("Aceptar")
        btn_aceptar.setFixedSize(130, 36)
        btn_aceptar.setStyleSheet("""
            QPushButton {
                background-color: #1B7C3D; 
                color: #FFFFFF; 
                font-weight: bold; 
                border: none; 
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #229A4C;
            }
        """)
        btn_aceptar.clicked.connect(self.accept)
        
        lay_btn = QHBoxLayout()
        lay_btn.addStretch()
        lay_btn.addWidget(btn_aceptar)
        lay_btn.addStretch()
        layout.addLayout(lay_btn)

    def _abrir_explorador(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de música", self.input_ruta.text())
        if carpeta:
            self.input_ruta.setText(carpeta)
            self.ruta_elegida = carpeta


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jerbawise Downloader")
        self.setMinimumSize(950, 620)
        
        ruta_icono = obtener_ruta("logo.ico")
        self.setWindowIcon(QIcon(ruta_icono))

        # ── GESTIÓN DEL PRIMER USO ──
        self.ruta_musica = cargar_config()
        
        if self.ruta_musica is None:
            ruta_defecto = Path.home() / "Music" / "Jerbawise"
            
            # Lanzamos exclusivamente nuestra ventana de bienvenida
            dialogo = DialogoBienvenida(str(ruta_defecto), self)
            dialogo.exec() 
            
            # Al cerrarse de forma segura, guardamos el resultado
            self.ruta_musica = Path(dialogo.ruta_elegida)
            guardar_config(self.ruta_musica)

        self.ruta_musica.mkdir(parents=True, exist_ok=True)

        self.canciones = []
        self.worker = None
        self._construir_ui()
        self._centrar_ventana()
        self._cargar_biblioteca()

    def _construir_ui(self):
        contenedor = QWidget()
        self.setCentralWidget(contenedor)
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        # ── Título ──
        titulo = QLabel("Jerbawise Downloader")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold; color: #1B7C3D;")
        layout.addWidget(titulo)

        # ── Barra de descarga ──
        barra_url = QHBoxLayout()
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Pega aquí un link de Spotify (canción o playlist)...")
        self.input_url.setFixedHeight(38)
        self.input_url.returnPressed.connect(self._iniciar_descarga)

        self.btn_descargar = QPushButton("Descargar")
        self.btn_descargar.setFixedSize(150, 38)
        self.btn_descargar.clicked.connect(self._iniciar_descarga)

        barra_url.addWidget(self.input_url)
        barra_url.addWidget(self.btn_descargar)
        layout.addLayout(barra_url)

        # ── Barra de progreso global ──
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setFixedHeight(4)
        self.barra_progreso.setTextVisible(False)
        self.barra_progreso.setVisible(False)
        layout.addWidget(self.barra_progreso)

        # ── Tabs ──
        self.tabs = QTabWidget()

        # Tab 1 — Biblioteca
        tab_biblioteca = QWidget()
        lay_bib = QVBoxLayout(tab_biblioteca)
        lay_bib.setContentsMargins(0, 8, 0, 0)
        lay_bib.setSpacing(6)

        barra_bib = QHBoxLayout()
        self.lbl_total = QLabel("0 canciones")
        self.lbl_total.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        
        self.lbl_ruta = QLabel(f"Carpeta: {self.ruta_musica}")
        self.lbl_ruta.setStyleSheet("color: #555555; font-size: 11px;")

        self.btn_carpeta = QPushButton("Cambiar carpeta")
        self.btn_carpeta.setFixedHeight(28)
        self.btn_carpeta.setStyleSheet("padding: 4px 12px; font-weight: normal;")
        self.btn_carpeta.clicked.connect(self._seleccionar_carpeta)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setFixedHeight(28)
        self.btn_actualizar.setStyleSheet("padding: 4px 12px; font-weight: normal;")
        self.btn_actualizar.clicked.connect(self._cargar_biblioteca)
        
        barra_bib.addWidget(self.lbl_total)
        barra_bib.addSpacing(15)
        barra_bib.addWidget(self.lbl_ruta)
        barra_bib.addStretch()
        barra_bib.addWidget(self.btn_carpeta)
        barra_bib.addWidget(self.btn_actualizar)
        lay_bib.addLayout(barra_bib)

        self.tabla_biblioteca = self._crear_tabla(["Título", "Artista", "Álbum", "Duración"])
        lay_bib.addWidget(self.tabla_biblioteca)
        self.tabs.addTab(tab_biblioteca, "Biblioteca")

        # Tab 2 — Descargas
        tab_descargas = QWidget()
        lay_desc = QVBoxLayout(tab_descargas)
        lay_desc.setContentsMargins(0, 8, 0, 0)
        self.tabla_descargas = self._crear_tabla(["Canción", "Artista", "Estado", "Hora"])
        lay_desc.addWidget(self.tabla_descargas)
        self.tabs.addTab(tab_descargas, "Descargas")

        layout.addWidget(self.tabs)

        # ── Estado ──
        self.lbl_estado = QLabel("Listo")
        self.lbl_estado.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(self.lbl_estado)

    def _crear_tabla(self, columnas):
        tabla = QTableWidget()
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(columnas)):
            tabla.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tabla.verticalHeader().setVisible(False)
        return tabla

    def _seleccionar_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de música", str(self.ruta_musica))
        if carpeta:
            self.ruta_musica = Path(carpeta)
            guardar_config(self.ruta_musica)
            self.lbl_ruta.setText(f"Carpeta: {self.ruta_musica}")
            self._cargar_biblioteca()

    def _cargar_biblioteca(self):
        self.lbl_estado.setText("Escaneando biblioteca...")
        self.canciones = escanear_biblioteca(self.ruta_musica)
        self.tabla_biblioteca.setRowCount(len(self.canciones))
        for fila, c in enumerate(self.canciones):
            mins, segs = divmod(c["duracion"], 60)
            self.tabla_biblioteca.setItem(fila, 0, QTableWidgetItem(c["titulo"]))
            self.tabla_biblioteca.setItem(fila, 1, QTableWidgetItem(c["artista"]))
            self.tabla_biblioteca.setItem(fila, 2, QTableWidgetItem(c["album"]))
            self.tabla_biblioteca.setItem(fila, 3, QTableWidgetItem(f"{mins}:{segs:02d}"))
        self.lbl_total.setText(f"{len(self.canciones)} canciones")
        self.lbl_estado.setText("Listo")

    def _iniciar_descarga(self):
        url = self.input_url.text().strip()
        if not url or self.worker is not None:
            return
        
        self.btn_descargar.setEnabled(False)
        self.btn_descargar.setText("Descargando...")
        self.barra_progreso.setVisible(True)
        self.lbl_estado.setText("Descargando contenido...")
        
        self.tabs.setCurrentIndex(1)
        self.input_url.clear()
        self.tabla_descargas.setRowCount(0)

        self.worker = DescargaWorker(url, self.ruta_musica)
        self.worker.cancion_descargada.connect(self._agregar_cancion_descargada)
        self.worker.cancion_saltada.connect(self._agregar_cancion_saltada)
        self.worker.cancion_error.connect(self._agregar_cancion_error)
        self.worker.terminado.connect(self._al_terminar_descarga)
        self.worker.start()

    def _agregar_fila(self, nombre: str, estado: str, color_hex: str):
        partes = nombre.split(" - ", 1)
        titulo  = partes[1].strip() if len(partes) == 2 else nombre
        artista = partes[0].strip() if len(partes) == 2 else "—"
        hora = QDateTime.currentDateTime().toString("HH:mm:ss")
        
        fila = self.tabla_descargas.rowCount()
        self.tabla_descargas.insertRow(fila)
        self.tabla_descargas.setItem(fila, 0, QTableWidgetItem(titulo))
        self.tabla_descargas.setItem(fila, 1, QTableWidgetItem(artista))
        self.tabla_descargas.setItem(fila, 2, QTableWidgetItem(estado))
        self.tabla_descargas.setItem(fila, 3, QTableWidgetItem(hora))
        
        color = QColor(color_hex)
        for col in range(4):
            item = self.tabla_descargas.item(fila, col)
            if item:
                item.setBackground(color)
                
        self.tabla_descargas.scrollToBottom()

    def _agregar_cancion_descargada(self, nombre: str):
        self._agregar_fila(nombre, "Descargada", "#145C2D") 

    def _agregar_cancion_saltada(self, nombre: str):
        self._agregar_fila(nombre, "Ya existe", "#111111") 

    def _agregar_cancion_error(self, nombre: str):
        self._agregar_fila(nombre, "Error", "#2A0808") 

    def _al_terminar_descarga(self, exito):
        self.btn_descargar.setEnabled(True)
        self.btn_descargar.setText("Descargar")
        self.barra_progreso.setVisible(False)
        self.lbl_estado.setText("Proceso finalizado ✓" if exito else "Finalizado con errores")
        
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        
        if exito:
            try:
                self._cargar_biblioteca()
            except Exception as e:
                self.lbl_estado.setText("Error al actualizar la biblioteca.")
                print(f"Error al escanear: {e}")

    def _centrar_ventana(self):
        pantalla = QApplication.primaryScreen().geometry()
        x = (pantalla.width()  - self.width())  // 2
        y = (pantalla.height() - self.height()) // 2
        self.move(x, y)


if __name__ == "__main__":
    try:
        myappid = 'jerbawise.downloader.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(obtener_ruta("logo.ico")))

    ruta_qss = obtener_ruta("estilo.qss")
    if os.path.exists(ruta_qss):
        with open(ruta_qss, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            
    ventana = MainWindow()
    ventana.show()
    sys.exit(app.exec())