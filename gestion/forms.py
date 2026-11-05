from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Consumo, Material, Proyecto, Usuario


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


class ConsumoForm(forms.ModelForm):
    class Meta:
        model = Consumo
        fields = ['material', 'cantidad', 'fecha']
        labels = {
            'material': 'Material u horas',
            'cantidad': 'Cantidad',
            'fecha': 'Fecha',
        }
        widgets = {
            'cantidad': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'inputmode': 'decimal'}),
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, categoria=None, **kwargs):
        # Igual que el formulario que recibe el request (Sesiones, diapositivas 26-27):
        # se le pasa un dato extra, la familia elegida, y con él se filtran los materiales.
        super().__init__(*args, **kwargs)
        materiales = Material.objects.order_by('nombre')
        if categoria:
            self.fields['material'].queryset = materiales.filter(categoria=categoria)
            self.fields['material'].empty_label = 'Elige material u horas'
        else:
            # Sin familia no se ofrece nada: primero se elige la familia
            self.fields['material'].queryset = materiales.none()
            self.fields['material'].empty_label = 'Elige primero una familia'

    def clean(self):
        super().clean()
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            self.add_error('cantidad', 'La cantidad tiene que ser mayor que 0.')
        return self.cleaned_data


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
        fields = ['nombre', 'categoria', 'unidad', 'precio']
        labels = {
            'nombre': 'Nombre',
            'categoria': 'Familia',
            'unidad': 'Unidad',
            'precio': 'Precio por unidad (€)',
        }
        error_messages = {
            'nombre': {'unique': 'Ya hay un material con ese nombre.'},
        }
        help_texts = {
            'precio': 'Cambiar el precio no modifica los apuntes ya hechos: cada apunte guarda el precio de su día.',
        }
        widgets = {
            'precio': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
        }

    def clean(self):
        super().clean()
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio < 0:
            self.add_error('precio', 'El precio no puede ser negativo.')
        return self.cleaned_data
