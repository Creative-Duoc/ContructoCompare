# ConstructoCompare

ConstructoCompare es una plataforma integral diseñada para el monitoreo y comparación de precios de materiales de construcción de diversos retailers. El sistema automatiza la recolección de datos, su procesamiento y su exposición a través de una API robusta.

## 🏗️ Arquitectura del Proyecto

El proyecto está dividido en tres componentes principales:

- **[Backend](./backend):** API REST construida con FastAPI, encargada de la lógica de negocio, autenticación y gestión de la base de datos (PostgreSQL + SQLAlchemy).
- **[Scrapers](./scrapers):** Scripts de automatización basados en Playwright para extraer información de productos de sitios web como Sodimac.
- **[Frontend](./frontend):** (En desarrollo) Interfaz de usuario para la visualización y comparación de los datos recolectados.

## 🚀 Inicio Rápido

### Requisitos Previos

- Python 3.13+
- PostgreSQL
- Node.js (para el futuro frontend)

### Instalación General

1. Clona el repositorio:
   ```bash
   git clone <url-del-repositorio>
   cd ContructoCompare
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Instala las dependencias globales:
   ```bash
   pip install -r requirement.txt
   ```

4. Instala los navegadores necesarios para Playwright:
   ```bash
   playwright install chromium
   ```

## 🛠️ Estructura de Directorios

```text
.
├── backend/          # API FastAPI y modelos de datos
├── frontend/         # Interfaz de usuario (React/Angular)
├── scrapers/         # Scripts de extracción de datos (Playwright)
├── database/         # Scripts DDL y esquemas SQL
└── requirement.txt   # Dependencias del proyecto
```

## 📝 Contribución

1. Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
2. Realiza tus cambios y haz commit (`git commit -m 'Añade nueva funcionalidad'`).
3. Sube los cambios (`git push origin feature/nueva-funcionalidad`).
4. Abre un Pull Request.
