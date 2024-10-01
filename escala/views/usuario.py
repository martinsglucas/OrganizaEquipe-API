from rest_framework.viewsets import ModelViewSet
from escala.serializers import UsuarioSerializer
from escala.models import Usuario
from escala.permissions import AllowPostWithoutAuthentication

class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']