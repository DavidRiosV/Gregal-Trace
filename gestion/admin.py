from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Albaran, Categoria, Cita, Consumo, Material, Nota, Oficina, Operario, Proyecto, Usuario


class UsuarioAdmin(UserAdmin):
    """Admin de usuarios de Django con el campo rol añadido.
    Se usa UserAdmin para que la contraseña se guarde cifrada al crear usuarios."""
    fieldsets = UserAdmin.fieldsets + (('Rol en Gregal Trace', {'fields': ('rol',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Rol en Gregal Trace', {'fields': ('rol',)}),)
    list_display = ('username', 'first_name', 'last_name', 'rol', 'is_active')


admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Operario)
admin.site.register(Oficina)
admin.site.register(Proyecto)
admin.site.register(Categoria)
admin.site.register(Material)
admin.site.register(Consumo)
admin.site.register(Albaran)
admin.site.register(Nota)
admin.site.register(Cita)
