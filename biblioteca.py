from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB

def leer_metadatos(ruta):
    try:
        tags = ID3(ruta)
        audio = MP3(ruta)
        return {
            "titulo":   str(tags.get("TIT2", ruta.stem)),
            "artista":  str(tags.get("TPE1", "Desconocido")),
            "album":    str(tags.get("TALB", "Desconocido")),
            "duracion": int(audio.info.length),
            "ruta":     ruta,
        }
    except Exception:
        return {
            "titulo":   ruta.stem,
            "artista":  "Desconocido",
            "album":    "Desconocido",
            "duracion": 0,
            "ruta":     ruta,
        }

def escanear_biblioteca(ruta):
    if not ruta.exists():
        return []

    canciones = []
    for archivo in ruta.rglob("*"):
        if archivo.suffix.lower() in (".mp3", ".flac", ".wav", ".m4a"):
            canciones.append(leer_metadatos(archivo))
    return canciones

if __name__ == "__main__":
    # Prueba rápida con la ruta de usuario por defecto
    ruta_prueba = Path.home() / "Music" / "Jerbawise"
    canciones = escanear_biblioteca(ruta_prueba)
    print(f"\nCanciones encontradas: {len(canciones)}\n")