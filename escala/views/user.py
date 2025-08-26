from rest_framework.viewsets import ModelViewSet
from escala.models import User, TeamInvitation, OrganizationInvitation
from escala.serializers import UserSerializer, RetrieveTeamInvitationSerializer, RetrieveOrganizationInvitationSerializer
from escala.permissions import AllowPostWithoutAuthentication
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']
    @extend_schema(
        responses={200: {"description": "Convites"}},
    )
    @action(detail=True, methods=['get'])
    def get_invitations(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        team_invitations = TeamInvitation.objects.all().filter(recipient_email=user.email)
        org_invitations = OrganizationInvitation.objects.all().filter(recipient_email=user.email)

        org_output = RetrieveOrganizationInvitationSerializer(org_invitations, many=True)

        team_output = RetrieveTeamInvitationSerializer(team_invitations, many=True)

        return Response({"team_invitations": team_output.data, "org_invitations": org_output.data}, status=status.HTTP_200_OK)