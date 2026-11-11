"""
python manage.py recuperar_citas

Vuelve a crear en la base de datos las citas guardadas en media/citas/proyecto_<id>.json.
Se usa después de borrar y recargar la base de datos (migrate + loaddata), igual que recuperar_albaranes.
"""
import json
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from gestion.models import Cita, Proyecto, Usuario


class Command(BaseCommand):
    help = 'Recupera las citas de media/citas/ que no están en la base de datos.'

    def handle(self, *args, **opciones):
        carpeta = Path(settings.MEDIA_ROOT) / 'citas'
        if not carpeta.exists():
            self.stdout.write('No hay carpeta media/citas: nada que recuperar.')
            return

        recuperadas = saltadas = 0
        for archivo in sorted(carpeta.glob('proyecto_*.json')):
            proyecto_id = int(archivo.stem.replace('proyecto_', ''))
            proyecto = Proyecto.objects.filter(pk=proyecto_id).first()
            citas = json.loads(archivo.read_text(encoding='utf-8'))
            if proyecto is None:
                self.stdout.write(self.style.WARNING(f'  {archivo.name}: el proyecto {proyecto_id} no existe. Se deja sin recuperar.'))
                saltadas += len(citas)
                continue
            for datos in citas:
                fecha = date.fromisoformat(datos['fecha'])
                hora = datetime.strptime(datos['hora'], '%H:%M').time() if datos.get('hora') else None
                # Si ya está (misma fecha, hora y motivo), no se duplica
                if Cita.objects.filter(proyecto=proyecto, fecha=fecha, hora=hora, motivo=datos.get('motivo', '')).exists():
                    continue
                Cita.objects.create(
                    proyecto=proyecto, fecha=fecha, hora=hora, motivo=datos.get('motivo', ''),
                    creada_por=Usuario.objects.filter(username=datos.get('creada_por', '')).first(),
                )
                recuperadas += 1
                self.stdout.write(f'  {fecha:%d/%m/%Y} {datos.get("motivo", "")} -> {proyecto.nombre}')

        self.stdout.write(self.style.SUCCESS(f'Citas recuperadas: {recuperadas}. Sin proyecto: {saltadas}.'))
