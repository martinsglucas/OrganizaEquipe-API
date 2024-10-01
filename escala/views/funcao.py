from rest_framework.viewsets import ModelViewSet
from escala.models import Funcao
from escala.serializers import FuncaoSerializer

class FuncaoViewSet(ModelViewSet):
    queryset = Funcao.objects.all()
    serializer_class = FuncaoSerializer
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']