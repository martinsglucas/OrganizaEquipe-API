from rest_framework.viewsets import ModelViewSet
from escala.models import User, TeamInvitation, OrganizationInvitation
from escala.serializers import UserSerializer, RetrieveTeamInvitationSerializer, RetrieveOrganizationInvitationSerializer
from escala.permissions import AllowPostWithoutAuthentication
from rest_framework.permissions import IsAuthenticated
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
    
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "fcm_token": {"type": "string", "description": "Token FCM do dispositivo"}
                },
                "required": ["fcm_token"]
            }
        },
        responses={200: {"description": "Token salvo com sucesso!"}},
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def fcm_token(self, request):
        fcm_token = request.data.get('fcm_token')

        if not fcm_token:
            return Response(
                {"error": "O campo 'fcm_token' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.fcm_token = fcm_token
        request.user.save()

        return Response({"message": "Token salvo com sucesso!"}, status=status.HTTP_200_OK)