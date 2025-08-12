from rest_framework.viewsets import ModelViewSet
from escala.models import Request, Team, Organization
from escala.serializers import RequestSerializer, CreateRequestSerializer

class RequestViewSet(ModelViewSet):
  queryset = Request.objects.all()
  serializer_class = RequestSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    code = self.request.query_params.get('codeAccess', None)
    
    if code:
      team = Team.objects.filter(code_access=code).first()
      organization = Organization.objects.filter(code_access=code).first()
      if not (team or organization):
        raise NotFound("Nenhuma equipe encontrada com esse código.")
      queryset = queryset.filter(code=code)
    
    return queryset

  def get_serializer_class(self):
    if self.action in ['create', 'update', 'partial_update', 'destroy']:
      return CreateRequestSerializer
    # elif self.action in ['update', 'partial_update', 'list', 'destroy', 'retrieve']:
    else:
      return RequestSerializer
    return super().get_serializer_class()