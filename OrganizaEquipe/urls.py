from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from escala.views import CustomTokenObtainPairView, UsuarioViewSet, FuncaoViewSet, OrganizacaoViewSet, EquipeViewSet, EscalaViewSet, IndisponibilidadeViewSet, ParticipacaoEscalaViewSet, ConviteViewSet, SolicitacaoViewSet
from rest_framework_simplejwt.views import TokenVerifyView

router = routers.DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)
router.register(r'organizacoes', OrganizacaoViewSet)
router.register(r'funcoes', FuncaoViewSet)
router.register(r'equipes', EquipeViewSet)
router.register(r'escalas', EscalaViewSet)
router.register(r'indisponibilidades', IndisponibilidadeViewSet)
router.register(r'participacoes', ParticipacaoEscalaViewSet)
router.register(r'convites', ConviteViewSet)
router.register(r'solicitacoes', SolicitacaoViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/', include(router.urls)),

]
