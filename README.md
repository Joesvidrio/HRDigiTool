# 🛠️ HR DigiTool

> Una herramienta de escritorio moderna, rápida e intuitiva diseñada para la digitalización, visualización y gestión de documentos PDF enfocada en recursos humanos.

---

## 📋 Tabla de Contenidos
- [Características Principales](#-características-principales)
- [Requisitos del Sistema](#-requisitos-del-sistema)
- [Instalación y Uso](#-instalación-y-uso)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Compilación Manual](#-compilación-manual)
- [Despliegue y CI/CD](#-despliegue-y-cicd)

---

## ✨ Características Principales

* 📖 **Lector e Inspector de PDFs:** Visualización fluida de documentos con herramientas de lectura dedicadas.
* 🧩 **Unión y Organización:** Fusiona múltiples archivos PDF o edita páginas en segundos.
* 🔒 **Seguridad:** Herramientas de protección, como eliminar metadatos o encriptar/desencriptar.
* 📂 **Integración con el Sistema:** Soporta la opción de asignación como **Lector de PDF predeterminado** (*Open With...*).

---

## 💻 Requisitos del Sistema

| Plataforma | Versión Mínima |
| :--- | :--- |
| **macOS** | macOS 11 (Big Sur) o posterior |
| **Windows** | Windows 10 / 11 (64-bit) |
| **Python** *(Desarrollo)* | Python 3.10+ |

---

## 🚀 Instalación y Uso

### Para Usuarios (Ejecutable)
1. Ve a la sección de **Releases** del repositorio.
2. Descarga la versión correspondiente a tu sistema operativo.
3. ¡Ejecuta y listo!

### Para Desarrolladores

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/TU_USUARIO/HRDigiTool.git
   cd HRDigiTool
   ```
2. **Crear y activar entorno virtual:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Ejecutar en modo desarrollo:**
   ```bash
   python main.py
   ```
---

## 📁 Estructura del Proyecto

```text
HRDigiTool/
├── .github/
│   └── workflows/      # Configuración de integración continua (CI/CD)
├── assets/             # Hojas de estilo QSS e imágenes
├── ui/                 # Componentes de la interfaz de usuario (PyQt6)
│   ├── views/          # Vistas individuales (Home, Reader, Merge, etc.)
│   └── main_window.py  # Ventana principal
├── utils.py            # Funciones auxiliares (rutas dinámicas de recursos)
├── main.py             # Punto de entrada principal de la aplicación
└── main_windows.spec   # Configuración de compilación para Windows
```

---

## 📦 Compilación Manual

Si deseas empaquetar la aplicación tú mismo con **PyInstaller**:
* **En Windows:**
  ```cmd
  pyinstaller main_windows.spec --clean
  ```
  *El ejecutable se generará en `dist/HRDigiTool/HRDigiTool.exe`.*

---

## ⚙️ Despliegue y CI/CD
El proyecto cuenta con **GitHub Actions** configurado en `.github/workflows/build_windows.yml`. Cada vez que se suben cambios a la rama `main`, los servidores de GitHub compilan automáticamente el archivo ejecutable para Windows y lo dejan disponible para su descarga en la pestaña **Actions > Artifacts**.
