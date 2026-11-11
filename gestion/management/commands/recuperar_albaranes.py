"""
python manage.py recuperar_albaranes

Vuelve a crear en la base de datos los albaranes cuyos PDF siguen en media/albaranes/.
Se usa después de borrar y recargar la base de datos (migrate + loaddata):
cada PDF está en la carpeta de su proyecto (proyecto_1104) y tiene al lado su ficha
(factura.pdf.json) con la descripción, quién lo subió y la fecha.
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from gestion.models import Albaran, Proyecto, Usuario


class Command(BaseCommand):
    help = 'Recupera los albaranes de media/albaranes/ que no están en la base de datos.'

    def handle(self, *args, **opciones):
        carpeta = Path(settings.MEDIA_ROOT) / 'albaranes'
        if not carpeta.exists():
            self.stdout.write('No hay carpeta media/albaranes: nada que recuperar.')
            return

        # Si en la ficha no está el usuario (o ya no existe), se pone a nombre de Oficina
        por_defecto = (Usuario.objects.filter(groups__name='Oficina').order_by('id').first()
                       or Usuario.objects.filter(is_superuser=True).order_by('id').first())
        ya_estan = set(Albaran.objects.values_list('archivo', flat=True))
        recuperados = saltados = 0

        for pdf in sorted(carpeta.glob('proyecto_*/*.pdf')):
            nombre = pdf.relative_to(settings.MEDIA_ROOT).as_posix()
            if nombre in ya_estan:
                continue
            ficha = {}
            ruta_ficha = pdf.with_name(pdf.name + '.json')
            if ruta_ficha.exists():
                ficha = json.loads(ruta_ficha.read_text(encoding='utf-8'))

            proyecto_id = int(pdf.parent.name.replace('proyecto_', ''))
            proyecto = Proyecto.objects.filter(pk=proyecto_id).first()
            if proyecto is None:
                self.stdout.write(self.style.WARNING(f'  {nombre}: el proyecto {proyecto_id} no existe. Se deja sin recuperar.'))
                saltados += 1
                continue

            usuario = Usuario.objects.filter(username=ficha.get('subido_por', '')).first() or por_defecto
            if usuario is None:
                self.stdout.write(self.style.ERROR('No hay ningún usuario de Oficina. Carga antes usuarios.json.'))
                return

            albaran = Albaran(proyecto=proyecto, descripcion=ficha.get('descripcion', ''), subido_por=usuario)
            albaran.archivo.name = nombre      # el PDF ya está en su sitio: solo se apunta a él
            albaran.save()
            # La fecha se pone después: auto_now_add pone siempre la de hoy al crear
            if ficha.get('fecha'):
                fecha = datetime.fromisoformat(ficha['fecha'])
            else:
                fecha = datetime.fromtimestamp(pdf.stat().st_mtime)
            Albaran.objects.filter(pk=albaran.pk).update(fecha=fecha)
            albaran.fecha = fecha
            albaran.guardar_ficha()
            recuperados += 1
            self.stdout.write(f'  {nombre} -> {proyecto.nombre}')

        self.stdout.write(self.style.SUCCESS(f'Albaranes recuperados: {recuperados}. Sin proyecto: {saltados}.'))
