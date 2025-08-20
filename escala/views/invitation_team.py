from rest_framework.viewsets import ModelViewSet
from escala.models import TeamInvitation
from escala.serializers import TeamInvitationSerializer, RetrieveTeamInvitationSerializer

class TeamInvitationViewSet(ModelViewSet):
  queryset = TeamInvitation.objects.all()
  
  def get_serializer_class(self):
    if self.action in ['list', 'retrieve']:
      return RetrieveTeamInvitationSerializer
    return TeamInvitationSerializer
    

  def get_queryset(self):
    queryset = super().get_queryset()
    recipient_email = self.request.query_params.get('addressee', None)

    if recipient_email:
      queryset = queryset.filter(recipient_email=recipient_email)

    return queryset