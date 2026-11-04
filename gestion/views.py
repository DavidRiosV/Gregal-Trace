from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ConsumoForm, MaterialForm, ProyectoForm, RegistroForm, UrgenciaForm
from .models import Consumo, Material, Oficina, Operario, Proyecto, Usuario

# Apartados de listado: traduce la palabra de la URL al código guardado en la base de datos.
# Urgencias no está aquí porque tiene su propia página (sirve para crear, no para buscar).
TIPOS = {
    'obras': {'codigo': 'OBR', 'titulo': 'Obras', 'nuevo': 'Nueva obra', 'imagen': 'img/categorias/obras.jpg'},
    'intervenciones': {'codigo': 'INT', 'titulo': 'Intervenciones', 'nuevo': 'Nueva intervención', 'imagen': 'img/categorias/intervenciones.jpg'},
    'mantenimientos': {'codigo': 'MAN', 'titulo': 'Mantenimientos', 'nuevo': 'Nuevo mantenimiento', 'imagen': 'img/categorias/mantenimientos.jpg'},
}


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
    proyectos = Proyecto.objects.filter(tipo=datos_tipo['codigo']).order_by('-fecha_inicio', '-id')

    # Filtro por estado: en proceso (por defecto), terminados o todos
    estado = request.GET.get('estado', 'PRO')
    if estado not in ('PRO', 'TER', 'todos'):
        estado = 'PRO'
    if estado != 'todos':
        proyectos = proyectos.filter(estado=estado)

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        proyectos = proyectos.filter(
            Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda)
        )

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

    if request.method == 'POST' and puede_apuntar:
        formulario = ConsumoForm(request.POST)
        if formulario.is_valid():
            consumo = formulario.save(commit=False)
            consumo.proyecto = proyecto
            consumo.trabajador = request.user
            consumo.precio_unitario = consumo.material.precio
            consumo.save()
            messages.success(
                request,
                f'Apuntado: {consumo.cantidad:g} {consumo.material.abreviatura()} de {consumo.material.nombre}.'
            )
            return redirect('detalle_proyecto', pk=proyecto.pk)
    else:
        formulario = ConsumoForm()

    consumos = proyecto.consumos.select_related('material', 'trabajador').order_by('-fecha', '-id')
    horas = consumos.filter(material__unidad='H').aggregate(total=Sum('cantidad'))['total'] or 0

    # Página a la que vuelve el botón de volver
    url_volver, slug, texto_volver = pagina_del_tipo(proyecto)

    contexto = {
        'proyecto': proyecto,
        'formulario': formulario,
        'consumos': consumos,
        'puede_apuntar': puede_apuntar,
        'url_volver': url_volver,
        'slug_volver': slug,
        'texto_volver': texto_volver,
        'horas': horas,
        # Marca en el menú el apartado al que pertenece el proyecto
        'seccion': slug or 'urgencias',
    }

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
            formulario.save()
            messages.success(request, f'«{proyecto.nombre}» actualizado.')
            return redirect('detalle_proyecto', pk=proyecto.pk)
    else:
        formulario = ProyectoForm(instance=proyecto)

    url_volver, slug, texto_volver = pagina_del_tipo(proyecto)
    return render(request, 'gestion/proyecto_form.html', {
        'formulario': formulario,
        'proyecto': proyecto,
        'titulo': f'Editar «{proyecto.nombre}»',
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
    # Borra también sus apuntes y albaranes (on_delete=CASCADE)
    proyecto.delete()
    messages.success(request, f'«{nombre}» eliminado de {texto_volver}.')
    if slug:
        return redirect(url_volver, tipo=slug)
    return redirect(url_volver)



# ---------------------------------------------------------------------------
# Editar y eliminar apuntes. El operario solo los suyos; Oficina, todos.
# ---------------------------------------------------------------------------
def puede_tocar_apunte(usuario, consumo):
    """Un apunte se puede cambiar si el proyecto sigue en proceso y es tuyo o eres Oficina."""
    if consumo.proyecto.esta_terminado():
        return False
    return consumo.trabajador == usuario or usuario.has_perm('gestion.change_proyecto')


@permission_required('gestion.change_consumo')
def consumo_editar(request, pk):
    consumo = get_object_or_404(Consumo.objects.select_related('proyecto', 'material'), pk=pk)
    if not puede_tocar_apunte(request.user, consumo):
        messages.error(request, 'Solo puedes cambiar tus propios apuntes y en proyectos que sigan en proceso.')
        return redirect('detalle_proyecto', pk=consumo.proyecto.pk)

    material_antes = consumo.material

    if request.method == 'POST':
        formulario = ConsumoForm(request.POST, instance=consumo)
        if formulario.is_valid():
            consumo = formulario.save(commit=False)
            # Si cambia el material se toma el precio de hoy; si no, se mantiene el congelado
            if consumo.material != material_antes:
                consumo.precio_unitario = consumo.material.precio
            consumo.save()
            messages.success(request, f'Apunte de {consumo.material.nombre} actualizado.')
            return redirect('detalle_proyecto', pk=consumo.proyecto.pk)
    else:
        formulario = ConsumoForm(instance=consumo)

    url_volver, slug, texto_volver = pagina_del_tipo(consumo.proyecto)
    return render(request, 'gestion/consumo_form.html', {
        'formulario': formulario,
        'consumo': consumo,
        'proyecto': consumo.proyecto,
        'url_volver': url_volver,
        'slug_volver': slug,
        'texto_volver': texto_volver,
        'seccion': slug or 'urgencias',
    })


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
            messages.error(request, 'Solo puedes eliminar tus propios apuntes y en proyectos que sigan en proceso.')
    return redirect('detalle_proyecto', pk=proyecto.pk)


# ---------------------------------------------------------------------------
# CRUD de materiales (Oficina)
# ---------------------------------------------------------------------------
@permission_required('gestion.change_material')
def lista_materiales(request):
    materiales = Material.objects.order_by('nombre')

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        materiales = materiales.filter(nombre__icontains=busqueda)

    return render(request, 'gestion/lista_materiales.html', {
        'materiales': materiales,
        'busqueda': busqueda,
        'seccion': 'materiales',
    })


@permission_required('gestion.add_material')
def material_crear(request):
    if request.method == 'POST':
        formulario = MaterialForm(request.POST)
        if formulario.is_valid():
            material = formulario.save()
            messages.success(request, f'Material «{material.nombre}» creado.')
            return redirect('lista_materiales')
    else:
        formulario = MaterialForm()

    return render(request, 'gestion/material_form.html', {
        'formulario': formulario,
        'titulo': 'Nuevo material',
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
            return redirect('lista_materiales')
    else:
        formulario = MaterialForm(instance=material)

    return render(request, 'gestion/material_form.html', {
        'formulario': formulario,
        'material': material,
        'titulo': f'Editar «{material.nombre}»',
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
    return redirect('lista_materiales')


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


def mi_error_404(request, exception=None):
    return render(request, 'errores/404.html', None, None, 404)


def mi_error_500(request):
    return render(request, 'errores/500.html', None, None, 500)
