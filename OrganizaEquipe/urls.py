from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from escala.views import CustomTokenObtainPairView, UserViewSet, RoleViewSet, OrganizationViewSet, TeamViewSet, ScheduleViewSet, UnavailabilityViewSet, ScheduleParticipationViewSet, TeamInvitationViewSet, OrganizationInvitationViewSet, RequestViewSet
from rest_framework_simplejwt.views import TokenVerifyView

router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'organizations', OrganizationViewSet)
router.register(r'roles', RoleViewSet)
router.register(r'teams', TeamViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'unavailability', UnavailabilityViewSet)
router.register(r'participations', ScheduleParticipationViewSet)
router.register(r'team_invitations', TeamInvitationViewSet)
router.register(r'organization_invitations', OrganizationInvitationViewSet)
router.register(r'requests', RequestViewSet)

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
