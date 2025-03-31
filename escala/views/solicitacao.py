from rest_framework.viewsets import ModelViewSet
from escala.models import Solicitacao, Equipe
from escala.serializers import SolicitacaoSerializer, CreateSolicitacaoSerializer

class SolicitacaoViewSet(ModelViewSet):
  queryset = Solicitacao.objects.all()
  serializer_class = SolicitacaoSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    codigo_equipe = self.request.query_params.get('codeAccess', None)
    
    if codigo_equipe:
      equipe = Equipe.objects.filter(codigo_de_acesso=codigo_equipe).first()
      if not equipe:
        raise NotFound("Nenhuma equipe encontrada com esse código.")
      queryset = queryset.filter(codigo_equipe=codigo_equipe)
    
    return queryset

  def get_serializer_class(self):
    if self.action in ['create', 'update', 'partial_update', 'destroy']:
      return CreateSolicitacaoSerializer
    # elif self.action in ['update', 'partial_update', 'list', 'destroy', 'retrieve']:
    else:
      return SolicitacaoSerializer
    return super().get_serializer_class()