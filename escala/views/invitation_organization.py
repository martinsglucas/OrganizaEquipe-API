from rest_framework.viewsets import ModelViewSet
from escala.models import OrganizationInvitation
from escala.serializers import OrganizationInvitationSerializer, RetrieveOrganizationInvitationSerializer

class OrganizationInvitationViewSet(ModelViewSet):
  queryset = OrganizationInvitation.objects.all()
  
  def get_serializer_class(self):
    if self.action in ['list', 'retrieve']:
      return RetrieveOrganizationInvitationSerializer
    return OrganizationInvitationSerializer

  def get_queryset(self):
    queryset = super().get_queryset()
    recipient_email = self.request.query_params.get('addressee', None)

    if recipient_email:
      queryset = queryset.filter(recipient_email=recipient_email)

    return queryset