from django.db.models import Count

from .models import Proyecto
from .views import TIPOS


def navegacion(request):
    """Contadores del menú, que necesitan todas las páginas. La sección activa la pasa cada vista."""
    if not request.user.is_authenticated:
        return {}

    conteo = {}
    for fila in Proyecto.objects.values('tipo', 'estado').annotate(n=Count('id')):
        conteo[(fila['tipo'], fila['estado'])] = fila['n']

    nav_tipos = {}
    for slug, datos in TIPOS.items():
        # Copia del diccionario para no modificar TIPOS
        copia = datos.copy()
        copia['en_proceso'] = conteo.get((datos['codigo'], 'PRO'), 0)
        copia['terminados'] = conteo.get((datos['codigo'], 'TER'), 0)
        nav_tipos[slug] = copia

    return {
        'nav_tipos': nav_tipos,
        'nav_urgencias': conteo.get(('URG', 'PRO'), 0),
    }
