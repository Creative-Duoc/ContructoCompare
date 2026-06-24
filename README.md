# ConstructoCompare

ConstructoCompare es una plataforma integral diseñada para el monitoreo y comparación de precios de materiales de construcción de diversos retailers. El sistema automatiza la recolección de datos, su procesamiento y su exposición a través de una API robusta.

## 👥 Estructura del Equipo y Roles

El proyecto fue planificado, desarrollado y certificado por el siguiente equipo técnico:

*   **Javiera Ramírez** – *Product Owner / Data Engineer*: Responsable del diseño y tuning del modelo de datos PostgreSQL, persistencia, lógica del ID Maestro y despliegue de infraestructura cloud.
*   **Samuel Bueno** – *Scrum Master / Backend Developer*: Desarrollador del Core API en FastAPI, lógica asíncrona de comparación y programación de los motores de ingesta (Scrapers).
*   **Israel González** – *Frontend Developer / UX Designer*: Diseñador de la interfaz progresiva con enfoque Mobile-First en Next.js, componentes analíticos, toggles de divisas (CLP/UF) y renderizado adaptativo.
*   **Genara Alarcón** – *QA Engineer / DevOps*: Responsable de la estrategia y ejecución de la matriz de pruebas (37 casos), auditorías de seguridad perimetral, logs de telemetría y validación del DoD.

## 🏗️ Arquitectura del Proyecto

El proyecto está dividido en cuatro componentes principales:

- **[Backend Inventory](./backend/inventory):** API REST para inventario y usuarios, con autenticación y acceso a la base de datos.
- **[Backend Quotes](./backend/quotes):** Microservicio FastAPI para CRUD de cotizaciones, con JWT compartido y base de datos compartida.
- **[Scrapers](./scrapers):** Scripts de automatización basados en Playwright para extraer información de productos de Sodimac, Easy e Imperial.
- **[Frontend](./frontend):** Prototipo funcional en Next.js para la visualización, comparación de precios en tiempo real (CLP/UF) y gestión de cotizaciones.

## 🚀 Inicio Rápido

### Requisitos Previos

- Python 3.13+
- PostgreSQL
- Node.js 

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
├── backend/           # Servicios backend
│   ├── inventory/     # API de inventario y usuarios
│   └── quotes/        # Microservicio de cotizaciones
├── frontend/         # Interfaz de usuario (React/Angular)
├── scrapers/         # Scripts de extracción de datos (Playwright)
└── requirement.txt   # Dependencias del proyecto
```

## ▶️ Servicios y Puertos

- Backend principal: http://localhost:8001
- Quotes Service: http://localhost:8002

El microservicio de cotizaciones expone:

- POST /api/v1/cotizaciones
- GET /api/v1/cotizaciones
- GET /api/v1/cotizaciones/{id}
- PUT /api/v1/cotizaciones/{id}
- DELETE /api/v1/cotizaciones/{id}

## 📝 Contribución

1. Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
2. Realiza tus cambios y haz commit (`git commit -m 'Añade nueva funcionalidad'`).
3. Sube los cambios (`git push origin feature/nueva-funcionalidad`).
4. Abre un Pull Request.
