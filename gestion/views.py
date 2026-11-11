from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.db.models import Count, F, Max, Min, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .calendario import descargar_ics, dias_del_evento, leer_eventos, url_outlook_web
from .forms import AlbaranForm, CategoriaForm, CitaForm, TipoForm, ConsumoForm, HorasForm, MaterialForm, NotaForm, ProyectoForm, RegistroForm, UrgenciaForm
from .models import Albaran, Categoria, Cita, guardar_citas_de, Consumo, Material, Nota, Oficina, Operario, Proyecto, Usuario, buscar_materiales, codigo_categoria, horas_texto

# Apartados de listado: traduce la palabra de la URL al código guardado en la base de datos.
# Urgencias no está aquí porque tiene su propia página (sirve para crear, no para buscar).
TIPOS = {
    'obras': {'codigo': 'OBR', 'titulo': 'Obras', 'nuevo': 'Nueva obra', 'imagen': 'img/procesos/obras.webp'},
    'intervenciones': {'codigo': 'INT', 'titulo': 'Intervenciones', 'nuevo': 'Nueva intervención', 'imagen': 'img/procesos/intervenciones.webp'},
    'mantenimientos': {'codigo': 'MAN', 'titulo': 'Mantenimientos', 'nuevo': 'Nuevo mantenimiento', 'imagen': 'img/procesos/mantenimientos.webp'},
}


def familia_elegida(request, por_defecto=''):
    """Familia de material que llega en la URL (?categoria=FON) o en el formulario.
    Si no es una de las del modelo, se ignora."""
    categoria = request.POST.get('categoria') or request.GET.get('categoria') or por_defecto
    if categoria and Categoria.objects.filter(pk=categoria).exists():
        return categoria
    return ''


def filtros_material(request, categoria_por_defecto=''):
    """Lo que ha elegido el usuario para encontrar el material: familia, tipo y texto buscado.
    Llega en la URL (GET) al pulsar los botones o en el formulario (POST) al apuntar."""
    categoria = familia_elegida(request, categoria_por_defecto)
    grupo = request.POST.get('grupo') or request.GET.get('grupo', '')
    busqueda = (request.POST.get('buscar') or request.GET.get('buscar', '')).strip()
    # Tipos que hay en la familia elegida, con cuántos materiales tiene cada uno
    grupos = []
    if categoria:
        # Las horas no salen aquí: tienen su propio apartado
        grupos = (Material.objects.filter(categoria=categoria).exclude(unidad='H')
                  .values('grupo').annotate(n=Count('id')).order_by('grupo'))
    return {
        # Lista de (código, nombre), como antes con choices; ahora sale de la tabla de familias
        'categorias': Categoria.objects.values_list('codigo', 'nombre'),
        'categoria_actual': categoria,
        'grupos': grupos,
        'grupo_actual': grupo,
        'busqueda_material': busqueda,
    }


def tipos_de_material():
    """Tipos que ya existen en el catálogo, para sugerirlos al crear o editar un material."""
    return Material.objects.exclude(grupo='').values_list('grupo', flat=True).distinct().order_by('grupo')


def proveedores_existentes():
    """Proveedores que ya existen en el catálogo, para sugerirlos al crear o editar un material."""
    return Material.objects.exclude(proveedor='').values_list('proveedor', flat=True).distinct().order_by('proveedor')


def url_con_filtros(nombre_url, pk, filtros):
    """URL de vuelta con los mismos filtros, para seguir apuntando desde el mismo sitio."""
    parametros = {}
    if filtros['busqueda_material']:
        parametros['buscar'] = filtros['busqueda_material']
    elif filtros['categoria_actual']:
        parametros['categoria'] = filtros['categoria_actual']
        if filtros['grupo_actual']:
            parametros['grupo'] = filtros['grupo_actual']
    url = reverse(nombre_url, args=[pk])
    if parametros:
        url += '?' + urlencode(parametros)
    return url


def clientes_existentes():
    """Clientes ya escritos en algún proyecto, para sugerirlos al crear o editar."""
    return Proyecto.objects.exclude(cliente='').values_list('cliente', flat=True).distinct().order_by('cliente')


def pagina_del_tipo(proyecto):
    """Listado al que pertenece un proyecto: (nombre de la URL, slug o None, texto)."""
    if proyecto.tipo == 'URG':
        return 'urgencias', None, 'Urgencias'
    for slug, datos in TIPOS.items():
        if datos['codigo'] == proyecto.tipo:
            return 'lista_proyectos', slug, datos['titulo']


@permission_required('gestion.view_proyecto')
def index(request):
    # Guarda en la sesión la hora en que entró por primera vez (Sesiones, diapositiva 5)
    if not 'fecha_inicio' in request.session:
        request.session['fecha_inicio'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    return render(request, 'gestion/index.html', {'tipos': TIPOS, 'seccion': 'inicio'})


@permission_required('gestion.view_proyecto')
def lista_proyectos(request, tipo):
    if tipo not in TIPOS:
        raise Http404('Tipo de proyecto no válido')

    datos_tipo = TIPOS[tipo]
    proyectos = Proyecto.objects.filter(tipo=datos_tipo['codigo'])

    # Filtro por estado: en proceso (por defecto), terminados o todos
    estado = request.GET.get('estado', 'PRO')
    if estado not in ('PRO', 'TER', 'todos'):
        estado = 'PRO'
    if estado != 'todos':
        proyectos = proyectos.filter(estado=estado)

    # Próxima cita de cada proyecto: la primera de hoy en adelante (las pasadas no cuentan)
    hoy = date.today()
    proyectos = proyectos.annotate(proxima_cita=Min('citas__fecha', filter=Q(citas__fecha__gte=hoy)))

    if estado == 'TER':
        # Terminados: el último que se terminó, primero
        proyectos = proyectos.order_by('-fecha_fin', '-id')
    else:
        # En proceso: primero el que tiene la cita más cercana; los que no tienen ninguna, al final
        proyectos = proyectos.order_by(F('proxima_cita').asc(nulls_last=True), '-fecha_inicio', '-id')

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        proyectos = proyectos.filter(
            Q(nombre__icontains=busqueda) | Q(cliente__icontains=busqueda) | Q(descripcion__icontains=busqueda)
        )

    # La próxima cita completa (con hora y motivo) de cada proyecto de la lista, en una sola consulta
    proyectos = list(proyectos)
    siguientes = {}
    for cita in Cita.objects.filter(proyecto__in=proyectos, fecha__gte=hoy).order_by('fecha', 'hora', 'id'):
        siguientes.setdefault(cita.proyecto_id, cita)
    for proyecto in proyectos:
        proyecto.siguiente_cita = siguientes.get(proyecto.pk)

    return render(request, 'gestion/lista_proyectos.html', {
        'proyectos': proyectos,
        'titulo': datos_tipo['titulo'],
        'nuevo': datos_tipo['nuevo'],
        'slug': tipo,
        'busqueda': busqueda,
        'estado_actual': estado,
        'seccion': tipo,
    })


@permission_required('gestion.add_proyecto')
def urgencias(request):
    if request.method == 'POST':
        formulario = UrgenciaForm(request.POST)
        if formulario.is_valid():
            urgencia = formulario.save(commit=False)
            urgencia.tipo = 'URG'
            urgencia.creado_por = request.user
            urgencia.save()
            autor = request.user.get_full_name() or request.user.username
            messages.success(
                request,
                f'Urgencia «{urgencia.nombre}» creada por {autor} el {urgencia.fecha_inicio:%d/%m/%Y}.'
            )
            return redirect('urgencias')
    else:
        formulario = UrgenciaForm()

    abiertas = Proyecto.objects.filter(tipo='URG', estado='PRO').select_related('creado_por').order_by('-fecha_inicio', '-id')

    return render(request, 'gestion/urgencias.html', {
        'formulario': formulario,
        'clientes': clientes_existentes(),
        'urgencias': abiertas,
        'seccion': 'urgencias',
    })


@permission_required('gestion.view_proyecto')
def detalle_proyecto(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.select_related('creado_por'), pk=pk)

    # Recuerda en la sesión el último proyecto que ha abierto (Sesiones, diapositiva 5)
    request.session['ultimo_proyecto'] = proyecto.pk
    request.session['ultimo_nombre'] = proyecto.nombre

    # Solo quien tiene permiso para añadir apuntes puede enviar el formulario
    puede_apuntar = request.user.has_perm('gestion.add_consumo') and not proyecto.esta_terminado()
    # Los operarios apuntan horas, notas y albaranes; el material lo apunta Oficina
    es_oficina = request.user.has_perm('gestion.change_proyecto')
    puede_apuntar_material = puede_apuntar and es_oficina

    # Primero se elige la familia (y si se quiere el tipo) o se busca por nombre;
    # el desplegable solo muestra esos materiales
    filtros = filtros_material(request)
    opciones = {
        'categoria': filtros['categoria_actual'],
        'grupo': filtros['grupo_actual'],
        'busqueda': filtros['busqueda_material'],
    }

    # Hay cuatro formularios en la página: horas, material, nota y albarán.
    # Un campo oculto («apunte») dice cuál se ha enviado.
    formulario = ConsumoForm(**opciones)
    formulario_horas = HorasForm()
    formulario_nota = NotaForm()
    formulario_albaran = AlbaranForm()
    formulario_cita = CitaForm()
    # Pestaña que se ve abajo al cargar (Apuntes, Notas o Albaranes)
    pestana = 'apuntes'
    enviado_a = request.POST.get('apunte') if request.method == 'POST' else None

    if enviado_a == 'cita' and request.user.has_perm('gestion.add_cita'):
        # Citas: las pone Oficina, también en proyectos terminados (una revisión, por ejemplo)
        formulario_cita = CitaForm(request.POST)
        if formulario_cita.is_valid():
            cita = formulario_cita.save(commit=False)
            cita.proyecto = proyecto
            cita.creada_por = request.user
            cita.save()
            messages.success(request, f'Cita añadida para el {cita.fecha:%d/%m/%Y} ({cita.dias()}).')
            return redirect(reverse('detalle_proyecto', args=[proyecto.pk]) + '#citas')

    elif enviado_a == 'nota' and request.user.has_perm('gestion.add_nota'):
        # Notas: cualquier usuario, también en proyectos terminados
        pestana = 'notas'
        formulario_nota = NotaForm(request.POST)
        if formulario_nota.is_valid():
            nota = formulario_nota.save(commit=False)
            nota.proyecto = proyecto
            nota.autor = request.user
            nota.save()
            messages.success(request, 'Nota añadida al proyecto.')
            return redirect(reverse('detalle_proyecto', args=[proyecto.pk]) + '#notas')

    elif enviado_a == 'albaran' and request.user.has_perm('gestion.add_albaran'):
        # Albaranes: el archivo llega en request.FILES (formulario con enctype multipart/form-data)
        pestana = 'albaranes'
        formulario_albaran = AlbaranForm(request.POST, request.FILES)
        if formulario_albaran.is_valid():
            albaran = formulario_albaran.save(commit=False)
            albaran.proyecto = proyecto
            albaran.subido_por = request.user
            albaran.save()
            messages.success(request, f'Albarán «{albaran.descripcion or albaran.nombre_archivo()}» subido.')
            return redirect(reverse('detalle_proyecto', args=[proyecto.pk]) + '#albaranes')

    elif request.method == 'POST' and puede_apuntar:
        if enviado_a != 'horas' and not puede_apuntar_material:
            # Un operario no puede apuntar material aunque envíe el formulario a mano
            messages.error(request, 'El material lo apunta Oficina. Tú puedes apuntar horas, notas y albaranes.')
            return redirect('detalle_proyecto', pk=proyecto.pk)
        if request.POST.get('apunte') == 'horas':
            enviado = formulario_horas = HorasForm(request.POST)
            volver = url_con_filtros('detalle_proyecto', proyecto.pk, filtros) + '#horas'
        else:
            enviado = formulario = ConsumoForm(request.POST, **opciones)
            # Vuelve con la misma familia y tipo abiertos, para seguir apuntando de ellos
            volver = url_con_filtros('detalle_proyecto', proyecto.pk, filtros) + '#apuntar'
        if enviado.is_valid():
            consumo = enviado.save(commit=False)
            consumo.proyecto = proyecto
            consumo.trabajador = request.user
            consumo.precio_unitario = consumo.material.precio
            consumo.save()
            messages.success(request, f'Apuntado: {consumo.cantidad_texto()} de {consumo.material.nombre}.')
            return redirect(volver)

    consumos = proyecto.consumos.select_related('material', 'trabajador').order_by('-fecha', '-id')
    horas = consumos.filter(material__unidad='H').aggregate(total=Sum('cantidad'))['total'] or 0

    # Página a la que vuelve el botón de volver
    url_volver, slug, texto_volver = pagina_del_tipo(proyecto)

    contexto = {
        'proyecto': proyecto,
        'formulario': formulario,
        'formulario_horas': formulario_horas,
        'formulario_nota': formulario_nota,
        'formulario_albaran': formulario_albaran,
        'formulario_cita': formulario_cita,
        # Citas: primero las que quedan (de la más cercana a la más lejana); luego las pasadas, de la más reciente
        'citas_proximas': proyecto.citas.filter(fecha__gte=date.today()),
        'citas_pasadas': proyecto.citas.filter(fecha__lt=date.today()).order_by('-fecha', '-hora'),
        'pestana': pestana,
        'notas': proyecto.notas.select_related('autor'),
        'albaranes': proyecto.albaranes.select_related('subido_por'),
        'consumos': consumos,
        'puede_apuntar': puede_apuntar,
        'puede_apuntar_material': puede_apuntar_material,
        'es_oficina': es_oficina,
        'url_volver': url_volver,
        'slug_volver': slug,
        'texto_volver': texto_volver,
        'horas': horas,
        'horas_texto': horas_texto(horas),
        # Marca en el menú el apartado al que pertenece el proyecto
        'seccion': slug or 'urgencias',
    }

    contexto.update(filtros)

    # El coste solo lo ve quien puede cambiar los precios (Oficina)
    if request.user.has_perm('gestion.change_material'):
        coste_total = 0
        for consumo in consumos:
            coste_total += consumo.total()
        contexto['coste_total'] = coste_total

    return render(request, 'gestion/detalle_proyecto.html', contexto)


@permission_required('gestion.change_proyecto')
def cambiar_estado(request, pk):
    """Oficina marca un proyecto como terminado o lo vuelve a poner en proceso."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    # Solo cambia si llega por POST (desde el botón); por un enlace (GET) no hace nada
    if request.method == 'POST':
        if proyecto.esta_terminado():
            proyecto.estado = 'PRO'
            proyecto.fecha_fin = None
            messages.success(request, f'«{proyecto.nombre}» vuelve a estar en proceso.')
        else:
            proyecto.estado = 'TER'
            proyecto.fecha_fin = date.today()
            # Una urgencia terminada pasa a su sección (obra, intervención o mantenimiento)
            if proyecto.oficializar_urgencia():
                proyecto.save()
                # Se lleva a Oficina a la sección donde ha quedado, con el filtro Terminados
                url_volver, slug, texto_volver = pagina_del_tipo(proyecto)
                messages.success(request, f'Urgencia «{proyecto.nombre}» terminada. Ya está en {texto_volver}, en Terminados, con todos sus apuntes.')
                url = reverse(url_volver, args=[slug])
                return redirect(f'{url}?estado=TER')
            messages.success(request, f'«{proyecto.nombre}» marcado como terminado.')
        proyecto.save()
    return redirect('detalle_proyecto', pk=proyecto.pk)



# ---------------------------------------------------------------------------
# CRUD de proyectos (Oficina). Crear, editar y eliminar (Formularios, diapositivas 35-84)
# ---------------------------------------------------------------------------
# Crear exige los dos permisos: los operarios tienen add_proyecto (para las
# urgencias), pero solo Oficina tiene además change_proyecto.
@permission_required('gestion.add_proyecto')
@permission_required('gestion.change_proyecto')
def proyecto_crear(request, tipo):
    if tipo not in TIPOS:
        raise Http404('Tipo de proyecto no válido')
    datos_tipo = TIPOS[tipo]

    if request.method == 'POST':
        formulario = ProyectoForm(request.POST)
        if formulario.is_valid():
            proyecto = formulario.save(commit=False)
            proyecto.creado_por = request.user
            proyecto.save()
            messages.success(request, f'«{proyecto.nombre}» creado en {proyecto.get_tipo_display()}.')
            return redirect('detalle_proyecto', pk=proyecto.pk)
    else:
        # El tipo viene marcado según la página desde la que se crea
        formulario = ProyectoForm(initial={'tipo': datos_tipo['codigo']})

    return render(request, 'gestion/proyecto_form.html', {
        'formulario': formulario,
        'titulo': datos_tipo['nuevo'],
        'clientes': clientes_existentes(),
        'url_volver': 'lista_proyectos',
        'slug_volver': tipo,
        'texto_volver': datos_tipo['titulo'],
        'seccion': tipo,
    })


@permission_required('gestion.change_proyecto')
def proyecto_editar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)

    if request.method == 'POST':
        # Mismo formulario que crear, pero con el proyecto que se edita (diapositiva 72)
        formulario = ProyectoForm(request.POST, instance=proyecto)
        if formulario.is_valid():
            proyecto = formulario.save(commit=False)
            # Si se edita una urgencia y se marca como terminada, también pasa a su sección
            if proyecto.esta_terminado() and proyecto.oficializar_urgencia():
                messages.success(request, f'Urgencia «{proyecto.nombre}» terminada. Ahora está en {proyecto.get_tipo_display()}.')
            else:
                messages.success(request, f'«{proyecto.nombre}» actualizado.')
            proyecto.save()
            return redirect('detalle_proyecto', pk=proyecto.pk)
    else:
        formulario = ProyectoForm(instance=proyecto)

    url_volver, slug, texto_volver = pagina_del_tipo(proyecto)
    return render(request, 'gestion/proyecto_form.html', {
        'formulario': formulario,
        'proyecto': proyecto,
        'titulo': f'Editar «{proyecto.nombre}»',
        'clientes': clientes_existentes(),
        'url_volver': url_volver,
        'slug_volver': slug,
        'texto_volver': texto_volver,
        'seccion': slug or 'urgencias',
    })


@permission_required('gestion.delete_proyecto')
def proyecto_eliminar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    # Solo se elimina desde el formulario (POST); por un enlace (GET) vuelve al detalle
    if request.method != 'POST':
        return redirect('detalle_proyecto', pk=proyecto.pk)

    url_volver, slug, texto_volver = pagina_del_tipo(proyecto)
    nombre = proyecto.nombre
    # Si era el último visitado, se borra de la sesión (Sesiones, diapositiva 7)
    if 'ultimo_proyecto' in request.session and request.session['ultimo_proyecto'] == proyecto.pk:
        del request.session['ultimo_proyecto']
        del request.session['ultimo_nombre']
    # Los PDF de sus albaranes se borran del disco; las filas las borra on_delete=CASCADE
    for albaran in proyecto.albaranes.all():
        albaran.borrar_archivos()
    # Borra también sus apuntes, notas, citas y albaranes (on_delete=CASCADE)
    proyecto_id = proyecto.pk
    proyecto.delete()
    # Y la copia de sus citas en el disco, que ya no tiene proyecto
    guardar_citas_de(proyecto_id)
    messages.success(request, f'«{nombre}» eliminado de {texto_volver}.')
    if slug:
        return redirect(url_volver, tipo=slug)
    return redirect(url_volver)



# ---------------------------------------------------------------------------
# Editar y eliminar apuntes. El operario solo los suyos; Oficina, todos.
# ---------------------------------------------------------------------------
def puede_tocar_apunte(usuario, consumo):
    """Un apunte se puede cambiar si el proyecto sigue en proceso y eres Oficina,
    o si es tuyo y es de horas (los operarios no apuntan material)."""
    if consumo.proyecto.esta_terminado():
        return False
    if usuario.has_perm('gestion.change_proyecto'):
        return True
    return consumo.trabajador == usuario and consumo.material.unidad == 'H'


@permission_required('gestion.change_consumo')
def consumo_editar(request, pk):
    consumo = get_object_or_404(Consumo.objects.select_related('proyecto', 'material'), pk=pk)
    if not puede_tocar_apunte(request.user, consumo):
        messages.error(request, 'Solo puedes cambiar tus propios apuntes de horas y en proyectos que sigan en proceso.')
        return redirect('detalle_proyecto', pk=consumo.proyecto.pk)

    material_antes = consumo.material
    # Por defecto se abre la familia del material que ya tiene el apunte
    filtros = filtros_material(request, consumo.material.categoria_id)
    opciones = {
        'categoria': filtros['categoria_actual'],
        'grupo': filtros['grupo_actual'],
        'busqueda': filtros['busqueda_material'],
    }

    # Un apunte de horas se edita con el selector de horas; uno de material, con la lista
    es_horas = material_antes.unidad == 'H'

    if request.method == 'POST':
        if es_horas:
            formulario = HorasForm(request.POST, instance=consumo)
        else:
            formulario = ConsumoForm(request.POST, instance=consumo, **opciones)
        if formulario.is_valid():
            consumo = formulario.save(commit=False)
            # Si cambia el material se toma el precio de hoy; si no, se mantiene el congelado
            if consumo.material != material_antes:
                consumo.precio_unitario = consumo.material.precio
            consumo.save()
            messages.success(request, f'Apunte de {consumo.material.nombre} actualizado.')
            return redirect('detalle_proyecto', pk=consumo.proyecto.pk)
    else:
        if es_horas:
            formulario = HorasForm(instance=consumo)
        else:
            formulario = ConsumoForm(instance=consumo, **opciones)

    url_volver, slug, texto_volver = pagina_del_tipo(consumo.proyecto)
    contexto = {
        'formulario': formulario,
        'es_horas': es_horas,
        'consumo': consumo,
        'proyecto': consumo.proyecto,
        'url_volver': url_volver,
        'slug_volver': slug,
        'texto_volver': texto_volver,
        'seccion': slug or 'urgencias',
    }
    contexto.update(filtros)
    return render(request, 'gestion/consumo_form.html', contexto)


@permission_required('gestion.delete_consumo')
def consumo_eliminar(request, pk):
    consumo = get_object_or_404(Consumo.objects.select_related('proyecto', 'material'), pk=pk)
    proyecto = consumo.proyecto

    if request.method == 'POST':
        if puede_tocar_apunte(request.user, consumo):
            nombre = consumo.material.nombre
            consumo.delete()
            messages.success(request, f'Apunte de {nombre} eliminado.')
        else:
            messages.error(request, 'Solo puedes eliminar tus propios apuntes de horas y en proyectos que sigan en proceso.')
    return redirect('detalle_proyecto', pk=proyecto.pk)


@permission_required('gestion.add_consumo')
def consumo_repetir(request, pk):
    """Apunta otra vez el mismo material y cantidad, con fecha de hoy y a nombre de quien lo pulsa."""
    original = get_object_or_404(Consumo.objects.select_related('proyecto', 'material'), pk=pk)
    proyecto = original.proyecto

    if request.method == 'POST':
        if proyecto.esta_terminado():
            messages.error(request, 'Este proyecto está terminado, así que ya no admite apuntes nuevos.')
        elif original.material.unidad != 'H' and not request.user.has_perm('gestion.change_proyecto'):
            messages.error(request, 'El material lo apunta Oficina. Tú puedes repetir apuntes de horas.')
        else:
            nuevo = Consumo.objects.create(
                proyecto=proyecto,
                material=original.material,
                cantidad=original.cantidad,
                # Precio de hoy, como cualquier apunte nuevo (no el del apunte original)
                precio_unitario=original.material.precio,
                trabajador=request.user,
                fecha=date.today(),
            )
            messages.success(request, f'Repetido: {nuevo.cantidad_texto()} de {nuevo.material.nombre}, con fecha de hoy.')
    return redirect(reverse('detalle_proyecto', args=[proyecto.pk]) + '#apuntes')


# ---------------------------------------------------------------------------
# Citas de un proyecto (Oficina las pone y las quita; todos las ven)
# ---------------------------------------------------------------------------
@permission_required('gestion.delete_cita')
def cita_eliminar(request, pk):
    cita = get_object_or_404(Cita.objects.select_related('proyecto'), pk=pk)
    if request.method == 'POST':
        fecha = cita.fecha
        cita.delete()
        messages.success(request, f'Cita del {fecha:%d/%m/%Y} eliminada.')
    return redirect(reverse('detalle_proyecto', args=[cita.proyecto.pk]) + '#citas')


# ---------------------------------------------------------------------------
# Notas de un proyecto. Las escribe cualquiera; se borran las propias (Oficina, todas).
# ---------------------------------------------------------------------------
@permission_required('gestion.delete_nota')
def nota_eliminar(request, pk):
    nota = get_object_or_404(Nota.objects.select_related('proyecto'), pk=pk)
    if request.method == 'POST':
        if nota.autor == request.user or request.user.has_perm('gestion.change_proyecto'):
            nota.delete()
            messages.success(request, 'Nota eliminada.')
        else:
            messages.error(request, 'Solo puedes eliminar tus propias notas.')
    return redirect(reverse('detalle_proyecto', args=[nota.proyecto.pk]) + '#notas')


# ---------------------------------------------------------------------------
# Albaranes en PDF. Los sube cualquiera desde el proyecto; Oficina los lista y los borra.
# ---------------------------------------------------------------------------
# Apartados del listado de albaranes: los tres de siempre y Urgencias (solo si tiene alguno)
SECCIONES_ALBARANES = {slug: datos for slug, datos in TIPOS.items()}
SECCIONES_ALBARANES['urgencias'] = {'codigo': 'URG', 'titulo': 'Urgencias'}


@permission_required('gestion.change_albaran')
def lista_albaranes(request):
    seccion = request.GET.get('tipo', 'obras')
    if seccion not in SECCIONES_ALBARANES:
        seccion = 'obras'

    # Cuántos albaranes hay en cada apartado. order_by() vacío: si no, el ordering del Meta rompe el GROUP BY
    conteo = {}
    for fila in Albaran.objects.values('proyecto__tipo').annotate(n=Count('id')).order_by():
        conteo[fila['proyecto__tipo']] = fila['n']

    pestanas = []
    for slug, datos in SECCIONES_ALBARANES.items():
        n = conteo.get(datos['codigo'], 0)
        if slug != 'urgencias' or n or seccion == 'urgencias':
            pestanas.append({'slug': slug, 'titulo': datos['titulo'], 'n': n})

    # Proyectos del apartado que tienen albaranes, con cuántos y la fecha del último
    proyectos = (Proyecto.objects.filter(tipo=SECCIONES_ALBARANES[seccion]['codigo'])
                 .annotate(num_albaranes=Count('albaranes'), ultimo_albaran=Max('albaranes__fecha'))
                 .filter(num_albaranes__gt=0)
                 .order_by('-ultimo_albaran'))

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        proyectos = proyectos.filter(Q(nombre__icontains=busqueda) | Q(cliente__icontains=busqueda))

    hoy = date.today()
    return render(request, 'gestion/albaranes.html', {
        'proyectos': proyectos,
        'pestanas': pestanas,
        'tipo_actual': seccion,
        'titulo_tipo': SECCIONES_ALBARANES[seccion]['titulo'],
        'busqueda': busqueda,
        'total_albaranes': sum(conteo.values()),
        'albaranes_mes': Albaran.objects.filter(fecha__year=hoy.year, fecha__month=hoy.month).count(),
        'seccion': 'albaranes',
    })


@permission_required('gestion.view_albaran')
def albaran_ver(request, pk):
    """Abre el PDF en el navegador. Pasa por aquí (y no por una URL pública de /media/)
    para que solo lo vean usuarios con sesión iniciada."""
    albaran = get_object_or_404(Albaran, pk=pk)
    try:
        archivo = albaran.archivo.open('rb')
    except FileNotFoundError:
        raise Http404('El PDF de este albarán ya no está en el servidor')
    return FileResponse(archivo, content_type='application/pdf', filename=albaran.nombre_archivo())


@permission_required('gestion.delete_albaran')
def albaran_eliminar(request, pk):
    albaran = get_object_or_404(Albaran.objects.select_related('proyecto'), pk=pk)
    proyecto = albaran.proyecto
    if request.method == 'POST':
        nombre = albaran.descripcion or albaran.nombre_archivo()
        # Primero el PDF y su ficha del disco, y después la fila de la base de datos
        albaran.borrar_archivos()
        albaran.delete()
        messages.success(request, f'Albarán «{nombre}» eliminado.')
    return redirect(reverse('detalle_proyecto', args=[proyecto.pk]) + '#albaranes')


# ---------------------------------------------------------------------------
# Familias del catálogo (Oficina): crear, renombrar, ordenar y eliminar
# ---------------------------------------------------------------------------
@permission_required('gestion.change_material')
def lista_categorias(request):
    # Crear una familia nueva desde el formulario de la misma página
    if request.method == 'POST':
        formulario = CategoriaForm(request.POST)
        if formulario.is_valid():
            categoria = formulario.save(commit=False)
            categoria.codigo = codigo_categoria(categoria.nombre)
            if categoria.codigo is None:
                formulario.add_error('nombre', 'No se ha podido crear un código para esta familia. Prueba con otro nombre.')
            else:
                categoria.save()
                messages.success(request, f'Familia «{categoria.nombre}» creada. Ya puedes elegirla al crear o editar un material.')
                return redirect('lista_categorias')
    else:
        # Por defecto, la nueva va antes de «Otros» (90)
        formulario = CategoriaForm(initial={'orden': 85})

    # order_by explícito: con annotate (GROUP BY) Django no aplica el ordering del Meta
    categorias = Categoria.objects.annotate(num_materiales=Count('materiales')).order_by('orden', 'nombre')
    return render(request, 'gestion/categorias.html', {
        'categorias': categorias,
        'formulario': formulario,
        'seccion': 'materiales',
    })


@permission_required('gestion.change_material')
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'POST':
        formulario = CategoriaForm(request.POST, instance=categoria)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, f'Familia «{categoria.nombre}» actualizada.')
            return redirect('lista_categorias')
    else:
        formulario = CategoriaForm(instance=categoria)

    return render(request, 'gestion/categoria_form.html', {
        'formulario': formulario,
        'categoria': categoria,
        'titulo': f'Editar «{categoria.nombre}»',
        'seccion': 'materiales',
    })


@permission_required('gestion.change_material')
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'POST':
        # Una familia con materiales no se puede borrar (on_delete=PROTECT en Material)
        num_materiales = categoria.materiales.count()
        if num_materiales:
            messages.error(request, f'«{categoria.nombre}» no se puede eliminar porque tiene {num_materiales} materiales. Pásalos antes a otra familia.')
        else:
            nombre = categoria.nombre
            categoria.delete()
            messages.success(request, f'Familia «{nombre}» eliminada.')
    return redirect('lista_categorias')


# ---------------------------------------------------------------------------
# Tipos de material (Oficina): el tipo es el texto «grupo» de cada material. Editar un tipo
# cambia de una vez todos los materiales que lo tienen.
# ---------------------------------------------------------------------------
@permission_required('gestion.change_material')
def lista_tipos(request):
    # Un tipo por cada pareja familia + grupo, con cuántos materiales tiene
    tipos = (Material.objects.exclude(grupo='')
             .values('categoria', 'categoria__nombre', 'grupo')
             .annotate(num_materiales=Count('id'))
             .order_by('categoria__orden', 'categoria__nombre', 'grupo'))

    filtro = familia_elegida(request)
    if filtro:
        tipos = tipos.filter(categoria=filtro)

    return render(request, 'gestion/tipos.html', {
        'tipos': tipos,
        'categorias': Categoria.objects.values_list('codigo', 'nombre'),
        'categoria_actual': filtro,
        'sin_tipo': Material.objects.filter(grupo='').count(),
        'seccion': 'materiales',
    })


@permission_required('gestion.change_material')
def tipo_editar(request):
    # El tipo se identifica por su familia y su nombre, que llegan en la URL (?categoria=FON&grupo=Bombas)
    categoria = get_object_or_404(Categoria, pk=request.GET.get('categoria', ''))
    grupo = request.GET.get('grupo', '')
    materiales = Material.objects.filter(categoria=categoria, grupo=grupo)
    if not grupo or not materiales.exists():
        raise Http404('Ese tipo no existe')

    if request.method == 'POST':
        formulario = TipoForm(request.POST)
        if formulario.is_valid():
            nuevo_nombre = formulario.cleaned_data['nombre']
            nueva_categoria = formulario.cleaned_data['categoria']
            # ¿Ya había un tipo con ese nombre en la familia de destino? Entonces se unen los dos
            se_une = (Material.objects.filter(categoria=nueva_categoria, grupo=nuevo_nombre)
                      .exclude(categoria=categoria, grupo=grupo).exists())
            # update(): cambia todos los materiales de golpe en una sola consulta
            cambiados = materiales.update(grupo=nuevo_nombre, categoria=nueva_categoria)
            if se_une:
                messages.success(request, f'«{grupo}» se ha unido a «{nuevo_nombre}» en {nueva_categoria.nombre} ({cambiados} materiales).')
            else:
                messages.success(request, f'Tipo «{nuevo_nombre}» guardado en {nueva_categoria.nombre} ({cambiados} materiales).')
            url = reverse('lista_tipos')
            return redirect(f'{url}?categoria={nueva_categoria.pk}')
    else:
        formulario = TipoForm(initial={'nombre': grupo, 'categoria': categoria})

    return render(request, 'gestion/tipo_form.html', {
        'formulario': formulario,
        'categoria': categoria,
        'grupo': grupo,
        'materiales': materiales.order_by('nombre'),
        'titulo': f'Editar el tipo «{grupo}»',
        'seccion': 'materiales',
    })


# ---------------------------------------------------------------------------
# Calendario (Oficina): el calendario de Outlook de la empresa junto a las citas de los proyectos
# ---------------------------------------------------------------------------
DIAS_CALENDARIO = 14


@permission_required('gestion.change_proyecto')
def calendario(request):
    hoy = date.today()
    # Primer día que se enseña (?desde=2026-11-10); si no llega o no es una fecha, hoy
    try:
        desde = datetime.strptime(request.GET.get('desde', ''), '%Y-%m-%d').date()
    except ValueError:
        desde = hoy
    hasta = desde + timedelta(days=DIAS_CALENDARIO - 1)

    # Qué se ve: todo, solo Outlook o solo las citas de los proyectos
    ver = request.GET.get('ver', 'todo')
    if ver not in ('todo', 'outlook', 'citas'):
        ver = 'todo'

    por_dia = {}
    for numero in range(DIAS_CALENDARIO):
        por_dia[desde + timedelta(days=numero)] = []

    error = ''
    if ver != 'citas':
        try:
            eventos = leer_eventos(descargar_ics())
        except (OSError, ValueError):
            # Sin internet, enlace caducado o calendario despublicado: se avisa y se siguen viendo las citas
            eventos = []
            error = 'Ahora mismo no se puede leer el calendario de Outlook. Se muestran solo las citas de los proyectos.'
        for evento in eventos:
            dias = list(dias_del_evento(evento))
            for numero, dia in enumerate(dias):
                if dia in por_dia:
                    # Un evento de varios días sale en cada uno; a partir del segundo, como «todo el día»
                    primer_dia = numero == 0
                    con_hora = not evento['todo_el_dia'] and primer_dia
                    por_dia[dia].append({
                        'fuente': 'outlook',
                        'titulo': evento['titulo'] or '(Sin título)',
                        'lugar': evento['lugar'],
                        'inicio': evento['inicio'] if con_hora else None,
                        'fin': evento['fin'] if con_hora and evento['fin'].date() == dia else None,
                        'varios_dias': f'Día {numero + 1} de {len(dias)}' if len(dias) > 1 else '',
                        'orden': evento['inicio'].strftime('%H:%M') if con_hora else '',
                    })

    if ver != 'outlook':
        for cita in Cita.objects.filter(fecha__range=(desde, hasta)).select_related('proyecto'):
            por_dia[cita.fecha].append({
                'fuente': 'cita',
                'titulo': cita.motivo or 'Cita',
                'proyecto': cita.proyecto,
                'inicio': cita.hora,
                'orden': cita.hora.strftime('%H:%M') if cita.hora else '',
            })

    # Días con algo (y hoy siempre); dentro de cada día, primero lo de todo el día y luego por hora
    dias = []
    for dia, elementos in por_dia.items():
        if elementos or dia == hoy:
            elementos.sort(key=lambda elemento: elemento['orden'])
            dias.append({'fecha': dia, 'elementos': elementos, 'es_hoy': dia == hoy})

    def url_desde(fecha):
        parametros = {'desde': fecha.isoformat()}
        if ver != 'todo':
            parametros['ver'] = ver
        return '?' + urlencode(parametros)

    return render(request, 'gestion/calendario.html', {
        'dias': dias,
        'desde': desde,
        'hasta': hasta,
        'ver_actual': ver,
        'error': error,
        'url_anterior': url_desde(desde - timedelta(days=DIAS_CALENDARIO)),
        'url_siguiente': url_desde(desde + timedelta(days=DIAS_CALENDARIO)),
        'url_hoy': url_desde(hoy),
        'es_desde_hoy': desde == hoy,
        'url_outlook': url_outlook_web(),
        'seccion': 'calendario',
    })


# ---------------------------------------------------------------------------
# Generador de presupuesto (Oficina) - versión futura, de prueba
# ---------------------------------------------------------------------------
@permission_required('gestion.change_material')
def generador_presupuesto(request):
    # Django solo sirve la página: el PDF se monta en el navegador con JavaScript (pdf-lib y pdf.js)
    return render(request, 'gestion/presupuestos.html', {'seccion': 'presupuestos'})


# ---------------------------------------------------------------------------
# CRUD de materiales (Oficina)
# ---------------------------------------------------------------------------
# Órdenes del listado de materiales (?orden=...). Por defecto, por familia.
ORDEN_MATERIALES = {
    # Por familia, tipo y nombre: así salen juntas las tuberías, las válvulas...
    'familia': ('categoria__orden', 'categoria__nombre', 'grupo', 'nombre'),
    'nombre': ('nombre',),
    'precio': ('precio', 'nombre'),
    '-precio': ('-precio', 'nombre'),
}

# Botones de clase: el código que viaja en la URL y el texto del botón
BOTONES_CLASE = [('PRI', 'Material principal'), ('ACC', 'Accesorios'), ('SOP', 'Soportes'), ('sin', 'Sin clase')]


def url_cambiando(request, **cambios):
    """La URL actual (?categoria=...&q=...) cambiando solo algunos parámetros. Los vacíos se quitan."""
    parametros = request.GET.dict()
    parametros.update(cambios)
    parametros = {clave: valor for clave, valor in parametros.items() if valor}
    return '?' + urlencode(parametros)


@permission_required('gestion.change_material')
def lista_materiales(request):
    materiales = Material.objects.select_related('categoria')

    # Filtro por familia (?categoria=FON) y por tipo (&grupo=Tuberías); sin filtro se ven todos
    filtros = filtros_material(request)
    if filtros['categoria_actual']:
        materiales = materiales.filter(categoria=filtros['categoria_actual'])
        if filtros['grupo_actual']:
            materiales = materiales.filter(grupo=filtros['grupo_actual'])

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        materiales = buscar_materiales(materiales, busqueda)

    # Cuántos hay de cada clase con los filtros de arriba, para los botones de clase
    conteo = {}
    for fila in materiales.values('clase').annotate(n=Count('id')).order_by():
        conteo[fila['clase'] or 'sin'] = fila['n']

    clase = request.GET.get('clase', '')
    if clase == 'sin':
        materiales = materiales.filter(clase='')
    elif clase in dict(Material.CLASES):
        materiales = materiales.filter(clase=clase)
    else:
        clase = ''

    botones_clase = [{'texto': 'Todas', 'n': sum(conteo.values()), 'url': url_cambiando(request, clase=''), 'activa': not clase}]
    for codigo, texto in BOTONES_CLASE:
        # «Sin clase» solo sale si hay alguno (mano de obra y servicios)
        if codigo != 'sin' or conteo.get('sin'):
            botones_clase.append({'codigo': codigo, 'texto': texto, 'n': conteo.get(codigo, 0),
                                  'url': url_cambiando(request, clase=codigo), 'activa': clase == codigo})

    orden = request.GET.get('orden', 'familia')
    if orden not in ORDEN_MATERIALES:
        orden = 'familia'
    materiales = materiales.order_by(*ORDEN_MATERIALES[orden])

    contexto = {
        'materiales': materiales,
        'busqueda': busqueda,
        'clase_actual': clase,
        'botones_clase': botones_clase,
        'orden_actual': orden,
        # Enlaces de las cabeceras de la tabla. Precio: si ya está de menor a mayor, el siguiente clic lo invierte
        'url_orden_nombre': url_cambiando(request, orden='nombre'),
        'url_orden_familia': url_cambiando(request, orden=''),
        'url_orden_precio': url_cambiando(request, orden='-precio' if orden == 'precio' else 'precio'),
        'seccion': 'materiales',
    }
    contexto.update(filtros)
    return render(request, 'gestion/lista_materiales.html', contexto)


@permission_required('gestion.add_material')
def material_crear(request):
    if request.method == 'POST':
        formulario = MaterialForm(request.POST)
        if formulario.is_valid():
            material = formulario.save()
            messages.success(request, f'Material «{material.nombre}» creado en {material.categoria.nombre}.')
            # «Guardar y añadir otro»: vuelve al formulario con la misma familia y unidad
            if 'otro' in request.POST:
                url = reverse('material_crear')
                return redirect(url + '?' + urlencode({'categoria': material.categoria_id, 'grupo': material.grupo, 'unidad': material.unidad}))
            url = reverse('lista_materiales')
            return redirect(f'{url}?categoria={material.categoria_id}')
    else:
        # Si se entra desde una familia filtrada, el formulario ya viene con ella marcada
        formulario = MaterialForm(initial={
            'categoria': familia_elegida(request, 'OTR'),
            'grupo': request.GET.get('grupo', ''),
            'unidad': request.GET.get('unidad', 'UD'),
        })

    return render(request, 'gestion/material_form.html', {
        'formulario': formulario,
        'categoria_actual': familia_elegida(request),
        'titulo': 'Nuevo material',
        'tipos': tipos_de_material(),
        'proveedores': proveedores_existentes(),
        'seccion': 'materiales',
    })


@permission_required('gestion.change_material')
def material_editar(request, pk):
    material = get_object_or_404(Material, pk=pk)

    if request.method == 'POST':
        formulario = MaterialForm(request.POST, instance=material)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, f'Material «{material.nombre}» actualizado.')
            # Vuelve a la lista con la familia del material abierta
            url = reverse('lista_materiales')
            return redirect(f'{url}?categoria={material.categoria_id}')
    else:
        formulario = MaterialForm(instance=material)

    return render(request, 'gestion/material_form.html', {
        'formulario': formulario,
        'material': material,
        'titulo': f'Editar «{material.nombre}»',
        'tipos': tipos_de_material(),
        'proveedores': proveedores_existentes(),
        'seccion': 'materiales',
    })


@permission_required('gestion.delete_material')
def material_eliminar(request, pk):
    material = get_object_or_404(Material, pk=pk)

    if request.method == 'POST':
        # Un material con apuntes no se puede borrar (on_delete=PROTECT en Consumo)
        num_apuntes = material.consumos.count()
        if num_apuntes:
            messages.error(request, f'«{material.nombre}» no se puede eliminar porque ya se ha usado en apuntes ({num_apuntes}). Puedes cambiarle el nombre o el precio.')
        else:
            nombre = material.nombre
            material.delete()
            messages.success(request, f'Material «{nombre}» eliminado.')
    url = reverse('lista_materiales')
    return redirect(f'{url}?categoria={material.categoria_id}')


def registrar_usuario(request):
    """Registro de un usuario nuevo (diapositivas 14 y 23)."""
    # Si ya ha iniciado sesión no tiene sentido registrarse (diapositiva 19)
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        formulario = RegistroForm(request.POST)
        if formulario.is_valid():
            user = formulario.save()
            # Según el rol elegido se crea un modelo u otro
            rol = int(formulario.cleaned_data.get('rol'))
            # Además se mete al usuario en su grupo de permisos (diapositiva 36)
            if rol == Usuario.OPERARIO:
                operario = Operario.objects.create(usuario=user)
                operario.save()
                grupo = Group.objects.get(name='Operarios')
                grupo.user_set.add(user)
            elif rol == Usuario.OFICINA:
                oficina = Oficina.objects.create(usuario=user)
                oficina.save()
                grupo = Group.objects.get(name='Oficina')
                grupo.user_set.add(user)
            # Entra directamente sin tener que hacer login
            login(request, user)
            messages.success(request, f'Bienvenido, {user.first_name}. Tu cuenta de operario ya está creada.')
            return redirect('index')
    else:
        formulario = RegistroForm()

    return render(request, 'registration/signup.html', {'formulario': formulario})


# ---------------------------------------------------------------------------
# Página oculta de pruebas: enlaces a todas las URLs para abrirlas rápido mientras se desarrolla 
# ---------------------------------------------------------------------------
# Solo Oficina puede verla 
@permission_required('gestion.change_proyecto')
def prueba(request):
    # Un ejemplo de cada para las URLs que piden un id (diapositiva 31: [:1])
    ejemplo = Proyecto.objects.order_by('id')[:1]
    ejemplo_consumo = Consumo.objects.order_by('id')[:1]
    ejemplo_material = Material.objects.order_by('id')[:1]
    return render(request, 'gestion/prueba.html', {
        'ejemplo': ejemplo,
        'ejemplo_consumo': ejemplo_consumo,
        'ejemplo_material': ejemplo_material,
    })


@permission_required('gestion.change_proyecto')
def prueba_error(request, codigo):
    """Muestra el diseño de una página de error aunque DEBUG sea True."""
    if codigo == 400:
        return mi_error_400(request)
    if codigo == 403:
        return mi_error_403(request)
    if codigo == 500:
        return mi_error_500(request)
    return mi_error_404(request)


# ---------------------------------------------------------------------------
# Páginas de error 
# ---------------------------------------------------------------------------
def mi_error_400(request, exception=None):
    return render(request, 'errores/400.html', None, None, 400)


def mi_error_403(request, exception=None):
    return render(request, 'errores/403.html', None, None, 403)


# ---------------------------------------------------------------------------
# App instalable en el móvil (PWA). Sin login: el navegador las pide antes de iniciar sesión.
# ---------------------------------------------------------------------------
def service_worker(request):
    # Se sirve desde /sw.js (no desde /static/) para que su alcance sea toda la web
    return render(request, 'gestion/sw.js', content_type='application/javascript')


def sin_conexion(request):
    return render(request, 'gestion/sin_conexion.html')


def mi_error_404(request, exception=None):
    return render(request, 'errores/404.html', None, None, 404)


def mi_error_500(request):
    return render(request, 'errores/500.html', None, None, 500)
