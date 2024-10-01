from rest_framework.viewsets import ModelViewSet
from escala.models import Equipe
from escala.serializers import CreateEquipeSerializer, EquipeSerializer, RetrieveEquipeSerializer

class EquipeViewSet(ModelViewSet):
    queryset = Equipe.objects.all()
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        
        if user_only:
            queryset = queryset.filter(membros=self.request.user)
        
        return queryset
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateEquipeSerializer
        elif self.action in ['update', 'partial_update', 'list', 'destroy']:
            return EquipeSerializer
        elif self.action == 'retrieve':
            return RetrieveEquipeSerializer
        return super().get_serializer_class()
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']