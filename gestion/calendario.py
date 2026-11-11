"""
Calendario de Outlook de la empresa (Oficina).

Outlook publica el calendario como un enlace .ics: un archivo de texto con un bloque
BEGIN:VEVENT ... END:VEVENT por cada evento. Este módulo lo descarga y saca de cada evento
el título, el lugar y las fechas. Es un «helper» (como el de los apuntes de API REST):
funciones de apoyo que no son vistas.

Solo se usa la biblioteca estándar de Python: Outlook ya publica cada repetición
(«todos los lunes») como un evento suelto, así que no hace falta una librería de calendarios.
"""
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache

# Outlook usa nombres de zona horaria de Windows; aquí se traducen a los de Python
ZONAS_WINDOWS = {
    'Romance Standard Time': 'Europe/Madrid',
    'W. Europe Standard Time': 'Europe/Berlin',
    'GMT Standard Time': 'Europe/London',
    'Central America Standard Time': 'America/Guatemala',
    'UTC': 'UTC',
}
MADRID = ZoneInfo('Europe/Madrid')
# Se guarda 10 minutos para no descargar el calendario en cada visita
SEGUNDOS_EN_CACHE = 600


def url_ics():
    return getattr(settings, 'OUTLOOK_ICS_URL', '')


def url_outlook_web():
    """La misma dirección acabada en .html abre el calendario en Outlook (para el botón «Abrir en Outlook»)."""
    url = url_ics()
    return url[:-4] + '.html' if url.endswith('.ics') else ''


def descargar_ics():
    """Texto del .ics. Lanza OSError si no hay enlace o no se puede descargar."""
    texto = cache.get('calendario_outlook')
    if texto is None:
        if not url_ics():
            raise OSError('No está configurado el enlace del calendario (OUTLOOK_ICS_URL en el .env).')
        with urllib.request.urlopen(url_ics(), timeout=10) as respuesta:
            texto = respuesta.read().decode('utf-8')
        cache.set('calendario_outlook', texto, SEGUNDOS_EN_CACHE)
    return texto


def desplegar_lineas(texto):
    """En un .ics las líneas largas se parten y la continuación empieza por un espacio: se vuelven a unir."""
    return texto.replace('\r\n ', '').replace('\r\n\t', '').replace('\n ', '').splitlines()


def desescapar(valor):
    r"""En los textos del .ics «\n» es un salto de línea y «\,» «\;» «\\» son la coma, el punto y coma y la barra."""
    return (valor.replace('\\n', '\n').replace('\\N', '\n')
            .replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\'))


def leer_fecha(parametros, valor):
    """Convierte DTSTART o DTEND en (fecha u hora de Madrid, es_todo_el_dia).
    Ejemplos: «VALUE=DATE» + «20261113» -> date; «TZID=UTC» + «20260702T100000» -> datetime en hora de Madrid."""
    if 'VALUE=DATE' in parametros or len(valor) == 8:
        return datetime.strptime(valor, '%Y%m%d').date(), True
    momento = datetime.strptime(valor.rstrip('Z'), '%Y%m%dT%H%M%S')
    if valor.endswith('Z'):
        zona = timezone.utc
    else:
        tzid = ''
        for parametro in parametros:
            if parametro.startswith('TZID='):
                tzid = parametro[5:].strip('"')
        zona = ZoneInfo(ZONAS_WINDOWS.get(tzid, 'Europe/Madrid'))
    # La web trabaja sin zonas horarias (USE_TZ = False): se pasa a hora de Madrid y se quita la zona
    return momento.replace(tzinfo=zona).astimezone(MADRID).replace(tzinfo=None), False


def leer_eventos(texto):
    """Lista de eventos del .ics, cada uno como diccionario. Los cancelados no se incluyen."""
    eventos = []
    evento = None
    for linea in desplegar_lineas(texto):
        if linea == 'BEGIN:VEVENT':
            evento = {}
        elif linea == 'END:VEVENT':
            if evento and 'inicio' in evento and evento.get('estado') != 'CANCELLED':
                eventos.append(evento)
            evento = None
        elif evento is not None and ':' in linea:
            # «DTSTART;TZID=UTC:20260702T100000» -> nombre DTSTART, parámetros [TZID=UTC], valor 20260702T100000
            cabeza, valor = linea.split(':', 1)
            nombre, *parametros = cabeza.split(';')
            if nombre == 'SUMMARY':
                evento['titulo'] = desescapar(valor).strip()
            elif nombre == 'LOCATION':
                evento['lugar'] = desescapar(valor).strip()
            elif nombre == 'STATUS':
                evento['estado'] = valor
            elif nombre == 'DTSTART':
                evento['inicio'], evento['todo_el_dia'] = leer_fecha(parametros, valor)
            elif nombre == 'DTEND':
                evento['fin'], _ = leer_fecha(parametros, valor)
    for evento in eventos:
        evento.setdefault('titulo', '')
        evento.setdefault('lugar', '')
        evento.setdefault('fin', evento['inicio'])
    return eventos


def dias_del_evento(evento):
    """Días en los que sale un evento. Los de día completo terminan el día ANTERIOR a su DTEND
    (un evento del 25/11 con DTEND 16/12 dura hasta el 15/12)."""
    if evento['todo_el_dia']:
        primero, ultimo = evento['inicio'], evento['fin'] - timedelta(days=1)
    else:
        primero, ultimo = evento['inicio'].date(), evento['fin'].date()
        # Si termina justo a medianoche, no se cuenta ese día
        if evento['fin'].time() == datetime.min.time() and ultimo > primero:
            ultimo -= timedelta(days=1)
    ultimo = max(primero, ultimo)
    dia = primero
    while dia <= ultimo:
        yield dia
        dia += timedelta(days=1)
