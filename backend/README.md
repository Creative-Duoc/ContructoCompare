# ⚙️ ConstructoCompare - Backend

El backend de ConstructoCompare es una API REST robusta construida con **FastAPI**. Gestiona la persistencia de datos, la lógica de inventario y la seguridad de los usuarios.

## 🚀 Tecnologías Principales

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (Asíncrono)
- **Base de Datos:** PostgreSQL
- **Seguridad:** JWT (JSON Web Tokens) con `passlib` y `python-jose`
- **Validación:** Pydantic 2.x

## 🛠️ Configuración y Uso

### 1. Variables de Entorno

Crea un archivo `.env` en el directorio `backend/` basándote en el archivo `.env.example`:

```bash
cp .env.example .env
```

Configura las siguientes variables:

```env
DATABASE_URL=postgresql+asyncpg://usuario:password@localhost:5432/constructo_db
AUTO_CREATE_TABLES=true
JWT_SECRET_KEY=una_clave_secreta_muy_segura
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 2. Ejecutar la API

Desde la raíz del proyecto (con el entorno virtual activo):

```bash
cd backend
python app/main.py
```

O usando uvicorn directamente:

```bash
uvicorn app.main:app --reload --port 8001
```

### 3. Documentación

Una vez iniciada la API, puedes acceder a la documentación interactiva en:

- **Swagger UI:** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- **ReDoc:** [http://127.0.0.1:8001/redoc](http://127.0.0.1:8001/redoc)

## 🔐 Flujo de Autenticación

La API utiliza seguridad basada en portadores (Bearer tokens):

1. **Registro:** `POST /api/v1/users/register`
2. **Login:** `POST /api/v1/users/login` (retorna un `access_token`)
3. **Acceso Protegido:** Incluye el header `Authorization: Bearer <tu_token>` en las peticiones a rutas protegidas.

## 📂 Estructura del Código

- `app/models/`: Definiciones de tablas de la base de datos.
- `app/routes/`: Definición de los endpoints de la API.
- `app/schemas/`: Modelos de validación Pydantic.
- `app/security.py`: Lógica de hash de contraseñas y gestión de tokens.
- `app/database.py`: Configuración de la conexión asíncrona a la DB.
