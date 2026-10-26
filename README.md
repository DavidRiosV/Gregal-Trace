<p align="center">
  <img src="gestion/static/img/logo.png" alt="Logo de Gregal Trace" width="96">
</p>

<h1 align="center">Gregal Trace</h1>

<p align="center">
  Registro del material y las horas de cada obra, intervención y mantenimiento,<br>
  apuntados desde donde se trabaja.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-desarrollo-003B57?logo=sqlite&logoColor=white">
  <img alt="Estado" src="https://img.shields.io/badge/estado-en%20desarrollo-689B41">
</p>

---

## Índice

- [Qué es](#qué-es)
- [Capturas](#capturas)
- [Funcionalidades](#funcionalidades)
- [Roles](#roles)
- [Tecnologías](#tecnologías)
- [Arquitectura](#arquitectura)
- [Modelo de datos](#modelo-de-datos)
- [Instalación y puesta en marcha](#instalación-y-puesta-en-marcha)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Hoja de ruta](#hoja-de-ruta)
- [Autor](#autor)

---

## Qué es

**Gregal Trace** es una aplicación web desarrollada con Django para **Instalaciones Gregal**. Sustituye algunas funciones que hoy cubren los CRM de la empresa.

- Los **operarios** apuntan, desde el móvil o el ordenador, el material y las horas que gastan en cada obra, intervención o mantenimiento.
- Si llega un trabajo urgente que aún no está dado de alta, el operario abre una **urgencia** y empieza a apuntar en ella.
- La **oficina** consulta todo lo apuntado, ve el coste de cada proyecto y lo marca como terminado cuando acaba.

Es el **Proyecto Integrado** del ciclo de Desarrollo de Aplicaciones Web (2.º DAW).

## Capturas

| Inicio de sesión | Inicio | Detalle de proyecto |
| :---: | :---: | :---: |
| ![Inicio de sesión](docs/img/login.png) | ![Inicio](docs/img/inicio.png) | ![Detalle de proyecto](docs/img/detalle.png) |

| Listado de obras | Urgencias | Versión móvil |
| :---: | :---: | :---: |
| ![Listado de obras](docs/img/listado.png) | ![Urgencias](docs/img/urgencias.png) | ![Versión móvil](docs/img/movil.png) |

## Funcionalidades

### Ya disponibles

- 🔐 **Inicio de sesión obligatorio**: ninguna página es accesible sin iniciar sesión.
- 🏗️ **Obras, Intervenciones y Mantenimientos** en secciones separadas, con buscador y filtro por estado (en proceso, terminados o todos).
- 🧾 **Apuntes de material y horas** en cada proyecto, registrando quién apuntó cada cosa y cuándo. Las horas de trabajo se tratan como un material más.
- 💶 **Precio congelado**: cada apunte guarda el precio del material en ese momento, así que el coste de un proyecto no cambia aunque después suba el precio.
- 🚨 **Urgencias**: abrir un trabajo que aún no está dado de alta, indicando si será obra, intervención o mantenimiento.
- ✅ **Estado del proyecto**: Oficina marca un proyecto como terminado; a partir de ahí no admite apuntes nuevos.
- 👁️ **Precios solo para Oficina**: los operarios no ven precios ni importes.
- 📱 **Diseño adaptado a móvil**, con menú lateral en escritorio y pestañas inferiores en móvil.

### En desarrollo

- Pedido de material desde el catálogo, con un Excel generado automáticamente y enviado al correo de la empresa.
- Registro de pedidos para Oficina, con filtros por trabajador, proyecto, tipo y fechas.
- Panel de gastos por proyecto con gráficas.
- Oficializar urgencias y subir albaranes.

## Roles

| | Operario | Oficina |
| --- | :---: | :---: |
| Ver obras, intervenciones y mantenimientos | ✅ | ✅ |
| Apuntar material y horas | ✅ | ✅ |
| Abrir urgencias | ✅ | ✅ |
| Ver quién hizo cada apunte | ✅ | ✅ |
| Ver precios, importes y coste total | ❌ | ✅ |
| Marcar un proyecto como terminado | ❌ | ✅ |

El panel de administración de Django (`/admin`) queda reservado al superusuario.

## Tecnologías

| Parte | Tecnología |
| --- | --- |
| Backend | Python 3.12 · Django 5.1 |
| Base de datos | SQLite (desarrollo) · PostgreSQL (producción, previsto) |
| Frontend | Plantillas de Django · CSS propio · JavaScript sin librerías |
| Excel | openpyxl (previsto) |
| Gráficas | Chart.js (previsto) |
| Diseño | Figma (wireframes) · draw.io (diagramas) |

## Arquitectura

Aplicación **monolítica** con el patrón **MTV** (Modelo, Plantilla, Vista) de Django, organizada en cinco capas:

1. **Cliente**: el navegador del móvil o del ordenador.
2. **Presentación**: plantillas de Django; `principal.html` es la base de la que heredan las demás.
3. **Control y lógica**: `urls.py`, `views.py`, `forms.py`, el middleware de login obligatorio y un procesador de contexto para el menú.
4. **Modelo**: `models.py` y el ORM de Django.
5. **Datos**: base de datos relacional y archivos subidos.

## Modelo de datos

![Diagrama entidad-relación](docs/img/modelo-er.png)

| Entidad | Para qué sirve |
| --- | --- |
| **Usuario** | Modelo `User` de Django, que gestiona el inicio de sesión |
| **Perfil** | Rol del usuario: Operario u Oficina (1:1 con Usuario) |
| **Proyecto** | Obra, intervención, mantenimiento o urgencia, con su estado |
| **Material** | Catálogo con unidad y precio; las horas son un material con unidad «hora» |
| **Consumo** | Cada apunte: qué material, cuánto, a qué precio, en qué proyecto y quién lo apuntó |
| **Albarán** | Documento subido y vinculado a un proyecto |

## Instalación y puesta en marcha

> Requisitos: **Python 3.12** y **Git**.

```bash
# 1. Clonar el repositorio
git clone https://github.com/DavidRiosV/Gregal-Trace-.git
cd Gregal-Trace-

# 2. Crear y activar el entorno virtual
python -m venv myvenv
myvenv\Scripts\activate          # Windows
# source myvenv/bin/activate     # Linux / macOS

# 3. Instalar las dependencias
pip install -r requirements.txt

# 4. Crear la base de datos
python manage.py migrate

# 5. (Opcional) Cargar los datos de ejemplo: proyectos terminados y catálogo de materiales
python manage.py loaddata datos_gregal

# 6. Crear el superusuario
python manage.py createsuperuser

# 7. Arrancar el servidor
python manage.py runserver
```

Después, abre <http://127.0.0.1:8000> en el navegador.

> **Nota:** para que un usuario entre como Operario u Oficina, créale un **Perfil** desde `/admin` y elige su rol.

## Estructura del proyecto

```text
Gregal-Trace-/
├── manage.py
├── requirements.txt
├── mysite/                  # Configuración del proyecto Django
│   ├── settings.py
│   └── urls.py
└── gestion/                 # Aplicación principal
    ├── models.py            # Perfil, Proyecto, Material, Consumo, Albarán
    ├── views.py             # Vistas y reglas de negocio
    ├── forms.py             # Formularios y validación
    ├── urls.py
    ├── context_processors.py
    ├── admin.py
    ├── fixtures/
    │   └── datos_gregal.json
    ├── migrations/
    ├── static/
    │   ├── css/estilos.css
    │   ├── js/main.js
    │   └── img/
    └── templates/
        ├── gestion/         # Páginas y plantillas reutilizables
        └── registration/    # Inicio de sesión
```

## Hoja de ruta

- [x] Análisis, requisitos y diseño (modelo de datos, arquitectura y wireframes)
- [x] Base del proyecto: usuarios, roles e inicio de sesión obligatorio
- [x] Apuntes de material y horas, urgencias y estado del proyecto
- [ ] Pedido de material desde el catálogo, con Excel y envío por correo
- [ ] Parte de Oficina: registro de pedidos, albaranes y panel de gastos
- [ ] Integración con Presto (BC3), de forma opcional
- [ ] Pruebas, despliegue en el servidor de la empresa y ajustes

## Autor

**David Ríos Valencia** · 2.º DAW, IES Polígono Sur (Sevilla)
Proyecto desarrollado durante las prácticas en **Instalaciones Gregal**.

[![GitHub](https://img.shields.io/badge/GitHub-DavidRiosV-181717?logo=github)](https://github.com/DavidRiosV)
