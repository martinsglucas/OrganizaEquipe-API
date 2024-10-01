from rest_framework.viewsets import ModelViewSet
from escala.models import ParticipacaoEscala
from escala.serializers import ParticipacaoEscalaSerializer, ParticipacaoEscalaRetrieveSerializer, ParticipacaoEscalaUpdateSerializer

class ParticipacaoEscalaViewSet(ModelViewSet):
    queryset = ParticipacaoEscala.objects.all()
    serializer_class = ParticipacaoEscalaSerializer
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ParticipacaoEscalaRetrieveSerializer
        if self.action in ['update', 'partial_update']:
            return ParticipacaoEscalaUpdateSerializer
        return ParticipacaoEscalaSerializer