from rest_framework.viewsets import ModelViewSet
from escala.models import Escala
from escala.serializers import CreateEscalaSerializer, RetrieveEscalaSerializer

class EscalaViewSet(ModelViewSet):
    queryset = Escala.objects.all()
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return CreateEscalaSerializer
        if self.action in ['list', 'retrieve']:
            return RetrieveEscalaSerializer
        return super().get_serializer
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']