from rest_framework.viewsets import ModelViewSet
from escala.models import Convite
from escala.serializers import ConviteSerializer

class ConviteViewSet(ModelViewSet):
  queryset = Convite.objects.all()
  serializer_class = ConviteSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    email_destinatario = self.request.query_params.get('addressee', None)

    if email_destinatario:
      queryset = queryset.filter(email_destinatario=email_destinatario)

    return queryset