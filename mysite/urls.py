from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('gestion.urls')),
]

# Páginas de error personalizadas (URLs, diapositiva 52)
handler400 = 'gestion.views.mi_error_400'
handler403 = 'gestion.views.mi_error_403'
handler404 = 'gestion.views.mi_error_404'
handler500 = 'gestion.views.mi_error_500'
