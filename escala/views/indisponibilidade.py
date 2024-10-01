from rest_framework.viewsets import ModelViewSet
from escala.models import Indisponibilidade
from escala.serializers import IndisponibilidadeSerializer, CreateIndisponibilidadeSerializer

class IndisponibilidadeViewSet(ModelViewSet):
    queryset = Indisponibilidade.objects.all()
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateIndisponibilidadeSerializer
        return IndisponibilidadeSerializer