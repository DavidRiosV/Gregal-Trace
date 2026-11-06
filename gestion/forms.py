from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Consumo, Material, Proyecto, Usuario, buscar_materiales


class RegistroForm(UserCreationForm):
    """Alta de usuarios (diapositiva 13). Hereda de UserCreationForm, que ya trae
    las dos contraseñas y sus validaciones."""
    # Solo se ofrece Operario: las cuentas de Oficina las crea la empresa desde /admin
    roles = (
        (Usuario.OPERARIO, 'Operario'),
    )
    rol = forms.ChoiceField(choices=roles, label='Rol')

    class Meta:
        model = Usuario
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'rol')
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
        }
        help_texts = {
            'username': 'Con él entrarás en la aplicación. Sin espacios.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El nombre aparece en cada apunte, así que es obligatorio
        self.fields['first_name'].required = True


class UrgenciaForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'tipo_destino', 'descripcion']
        labels = {
            'nombre': 'Nombre o dirección del trabajo',
            'tipo_destino': '¿Qué es?',
            'descripcion': 'Descripción',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo puede convertirse en Obra, Intervención o Mantenimiento, y es obligatorio
        self.fields['tipo_destino'].choices = [
            ('', 'Elige una opción'),
            ('OBR', 'Obra'),
            ('INT', 'Intervención'),
            ('MAN', 'Mantenimiento'),
        ]
        self.fields['tipo_destino'].required = True


class ApunteForm(forms.ModelForm):
    """Base de los dos formularios de apuntar: mismos campos y misma validación."""
    class Meta:
        model = Consumo
        fields = ['material', 'cantidad', 'fecha']
        labels = {
            'material': 'Material',
            'cantidad': 'Cantidad',
            'fecha': 'Fecha',
        }
        widgets = {
            'cantidad': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'inputmode': 'decimal'}),
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean(self):
        super().clean()
        cantidad = self.cleaned_data.get('cantidad')
        material = self.cleaned_data.get('material')
        if cantidad is not None and cantidad <= 0:
            self.add_error('cantidad', 'La cantidad tiene que ser mayor que 0.')
        elif cantidad is not None and material and material.unidad == 'H':
            # Horas: de 15 en 15 minutos y como mucho una jornada de 24 h
            if cantidad > 24:
                self.add_error('cantidad', 'No se pueden apuntar más de 24 horas en un apunte.')
            elif (cantidad * 4) % 1 != 0:
                self.add_error('cantidad', 'Las horas se apuntan en tramos de 15 minutos (00, 15, 30 o 45).')
        return self.cleaned_data


class ConsumoForm(ApunteForm):
    """Apuntar material. Las horas tienen su propio formulario (HorasForm)."""

    def __init__(self, *args, categoria=None, grupo=None, busqueda=None, **kwargs):
        # Igual que el formulario que recibe el request (Sesiones, diapositivas 26-27):
        # se le pasan datos extra (familia, tipo y búsqueda) y con ellos se filtran los materiales.
        super().__init__(*args, **kwargs)
        materiales = Material.objects.exclude(unidad='H').order_by('grupo', 'nombre')
        if busqueda:
            # El buscador mira en todo el catálogo, sin importar la familia
            materiales = buscar_materiales(materiales, busqueda)
        elif categoria:
            materiales = materiales.filter(categoria=categoria)
            if grupo:
                materiales = materiales.filter(grupo=grupo)
        else:
            # Sin familia ni búsqueda todavía no se ofrece nada
            materiales = materiales.none()
        self.fields['material'].queryset = materiales

        # Lista para la plantilla: los materiales agrupados por tipo (Tuberías, Válvulas...)
        self.agrupados = {}
        for material in materiales:
            self.agrupados.setdefault(material.grupo or 'Otros', []).append(material)
        # Si solo hay un material posible, se deja marcado
        if len(materiales) == 1 and not self.is_bound and not self.instance.pk:
            self.initial['material'] = materiales[0].pk


class HorasForm(ApunteForm):
    """Apuntar horas de trabajo: tipo de hora (Oficial o Pareja) y cuánto tiempo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        horas = Material.objects.filter(unidad='H').order_by('nombre')
        # Botones de opción en vez de desplegable, sin la opción vacía «---------»
        self.fields['material'].widget = forms.RadioSelect()
        self.fields['material'].empty_label = None
        # En los botones sale «Oficial» y «Pareja» en vez de «Hora Oficial (Hora)»
        self.fields['material'].label_from_instance = lambda material: material.nombre.replace('Hora ', '')
        self.fields['material'].queryset = horas
        self.fields['material'].label = 'Tipo de hora'
        # La cantidad la escribe el selector de horas y minutos (main.js)
        self.fields['cantidad'].widget = forms.HiddenInput()
        if not self.is_bound and not self.instance.pk:
            self.initial['cantidad'] = 1
            if horas:
                self.initial['material'] = horas[0].pk


class ProyectoForm(forms.ModelForm):
    """Crear y editar obras, intervenciones, mantenimientos y urgencias (Oficina)."""
    class Meta:
        model = Proyecto
        fields = ['nombre', 'tipo', 'descripcion', 'fecha_inicio', 'fecha_fin', 'estado']
        labels = {
            'nombre': 'Nombre o dirección',
            'tipo': 'Tipo',
            'descripcion': 'Descripción',
            'fecha_inicio': 'Fecha de inicio',
            'fecha_fin': 'Fecha de fin',
            'estado': 'Estado',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean(self):
        # Primero la validación normal de Django (diapositiva 43)
        super().clean()

        fecha_inicio = self.cleaned_data.get('fecha_inicio')
        fecha_fin = self.cleaned_data.get('fecha_fin')
        estado = self.cleaned_data.get('estado')

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error('fecha_fin', 'La fecha de fin no puede ser anterior a la de inicio.')

        if estado == 'TER' and not fecha_fin:
            self.add_error('fecha_fin', 'Un proyecto terminado necesita fecha de fin.')

        if estado == 'PRO' and fecha_fin:
            self.add_error('fecha_fin', 'Un proyecto en proceso no lleva fecha de fin. Déjala vacía o márcalo como terminado.')

        return self.cleaned_data


class MaterialForm(forms.ModelForm):
    """Catálogo de materiales y horas (Oficina)."""
    class Meta:
        model = Material
        fields = ['nombre', 'categoria', 'grupo', 'unidad', 'precio']
        labels = {
            'nombre': 'Nombre',
            'categoria': 'Familia',
            'grupo': 'Tipo',
            'unidad': 'Unidad',
            'precio': 'Precio por unidad (€)',
        }
        error_messages = {
            'nombre': {'unique': 'Ya hay un material con ese nombre.'},
        }
        help_texts = {
            'grupo': 'Por ejemplo Tuberías, Válvulas o Bombas. Elige uno de la lista o escribe uno nuevo.',
            'precio': 'Cambiar el precio no modifica los apuntes ya hechos: cada apunte guarda el precio de su día.',
        }
        widgets = {
            # list= enlaza el campo con el <datalist> de tipos que ya existen (sugerencias al escribir)
            'grupo': forms.TextInput(attrs={'list': 'tipos-material', 'autocomplete': 'off'}),
            'precio': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
        }

    def clean(self):
        super().clean()
        # El tipo empieza siempre en mayúscula para que «tuberías» y «Tuberías» sean el mismo
        grupo = self.cleaned_data.get('grupo')
        if grupo:
            grupo = ' '.join(grupo.split())
            self.cleaned_data['grupo'] = grupo[:1].upper() + grupo[1:]
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio < 0:
            self.add_error('precio', 'El precio no puede ser negativo.')
        return self.cleaned_data
