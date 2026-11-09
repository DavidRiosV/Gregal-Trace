from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('prueba/', views.prueba, name='prueba'),
    path('prueba/error/<int:codigo>/', views.prueba_error, name='prueba_error'),
    path('registrar/', views.registrar_usuario, name='registrar_usuario'),
    path('proyectos/<slug:tipo>/', views.lista_proyectos, name='lista_proyectos'),
    path('urgencias/', views.urgencias, name='urgencias'),
    path('proyecto/<int:pk>/', views.detalle_proyecto, name='detalle_proyecto'),
    path('proyecto/<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),
    path('proyectos/<slug:tipo>/nuevo/', views.proyecto_crear, name='proyecto_crear'),
    path('proyecto/<int:pk>/editar/', views.proyecto_editar, name='proyecto_editar'),
    path('proyecto/<int:pk>/eliminar/', views.proyecto_eliminar, name='proyecto_eliminar'),
    path('apunte/<int:pk>/editar/', views.consumo_editar, name='consumo_editar'),
    path('apunte/<int:pk>/eliminar/', views.consumo_eliminar, name='consumo_eliminar'),
    path('materiales/', views.lista_materiales, name='lista_materiales'),
    path('presupuestos/', views.generador_presupuesto, name='generador_presupuesto'),
    path('materiales/nuevo/', views.material_crear, name='material_crear'),
    path('material/<int:pk>/editar/', views.material_editar, name='material_editar'),
    path('material/<int:pk>/eliminar/', views.material_eliminar, name='material_eliminar'),
]