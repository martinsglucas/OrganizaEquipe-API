from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema
from escala.models import Team, TeamJoinRequest
from escala.serializers import CreateTeamSerializer, TeamDiscoverySerializer, TeamJoinRequestSerializer, TeamSerializer, RetrieveTeamSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from datetime import datetime

class TeamViewSet(ModelViewSet):
    queryset = Team.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        code_access = self.request.query_params.get('codeAccess', None)
        
        if user_only:
            queryset = queryset.filter(members=self.request.user)
        if code_access:
            queryset = queryset.filter(
                code_access=code_access,
                organization__members=self.request.user,
            )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTeamSerializer
        elif self.action in ['update', 'partial_update', 'list', 'destroy']:
            return TeamSerializer
        elif self.action == 'retrieve':
            return RetrieveTeamSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def discoverable(self, request):
        teams = Team.objects.filter(
            organization__members=request.user,
        ).exclude(
            members=request.user,
        ).exclude(
            id__in=TeamJoinRequest.objects.filter(
                user=request.user,
                status=TeamJoinRequest.Status.PENDING,
            ).values('team_id'),
        ).order_by('name').distinct()
        return Response(TeamDiscoverySerializer(teams, many=True).data)

    @action(detail=False, methods=['get'], url_path='my_join_requests')
    def my_join_requests(self, request):
        join_requests = TeamJoinRequest.objects.filter(user=request.user).select_related(
            'team',
            'user',
            'reviewed_by',
        )
        return Response(TeamJoinRequestSerializer(join_requests, many=True).data)

    @action(detail=True, methods=['post'])
    def request_join(self, request, pk=None):
        team = self.get_object()
        if not team.organization.members.filter(id=request.user.id).exists():
            raise PermissionDenied('Você só pode solicitar equipes da sua organização.')
        if team.members.filter(id=request.user.id).exists():
            raise ValidationError('Você já faz parte desta equipe.')
        if TeamJoinRequest.objects.filter(
            user=request.user,
            team=team,
            status=TeamJoinRequest.Status.PENDING,
        ).exists():
            raise ValidationError('Já existe uma solicitação pendente para esta equipe.')

        join_request = TeamJoinRequest.objects.create(user=request.user, team=team)
        return Response(
            TeamJoinRequestSerializer(join_request).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def join_requests(self, request, pk=None):
        team = self.get_object()
        self._require_team_admin(team, request.user)
        join_requests = team.join_requests.filter(
            status=TeamJoinRequest.Status.PENDING,
        ).select_related('team', 'user', 'reviewed_by')
        return Response(TeamJoinRequestSerializer(join_requests, many=True).data)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'join_requests/(?P<request_id>[^/.]+)/approve',
    )
    def approve_join_request(self, request, pk=None, request_id=None):
        team = self.get_object()
        self._require_team_admin(team, request.user)
        join_request = get_object_or_404(TeamJoinRequest, pk=request_id, team=team)
        join_request.approve(request.user)
        join_request.refresh_from_db()
        return Response(TeamJoinRequestSerializer(join_request).data)

    @action(
        detail=True,
        methods=['post'],
        url_path=r'join_requests/(?P<request_id>[^/.]+)/reject',
    )
    def reject_join_request(self, request, pk=None, request_id=None):
        team = self.get_object()
        self._require_team_admin(team, request.user)
        join_request = get_object_or_404(TeamJoinRequest, pk=request_id, team=team)
        join_request.reject(request.user)
        join_request.refresh_from_db()
        return Response(TeamJoinRequestSerializer(join_request).data)

    @staticmethod
    def _require_team_admin(team, user):
        if not team.admins.filter(id=user.id).exists():
            raise PermissionDenied('Apenas admins da equipe podem revisar solicitações.')
        
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID do usuário a ser adicionado"}
                },
                "required": ["user_id"]
            }
        },
        responses={200: {"description": "Usuário adicionado com sucesso!"}},
    )
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        team = get_object_or_404(Team, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if team.members.filter(id=user_id).exists():
            return Response({"message": "Usuário já faz parte da equipe."}, status=status.HTTP_200_OK)
        team.members.add(user_id)
        team.save()

        return Response({"message": "Usuário adicionado com sucesso!"}, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID do usuário a ser removido"}
                },
                "required": ["user_id"]
            }
        },
        responses={200: {"description": "Usuário removido com sucesso!"}},
    )
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        team = get_object_or_404(Team, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if not team.members.filter(id=user_id).exists():
            return Response({"message": "Usuário não encontrado na equipe."}, status=status.HTTP_404_NOT_FOUND)
        team.members.remove(user_id)
        if team.admins.filter(id=user_id).exists():
            team.admins.remove(user_id)
        team.save()

        return Response({"message": "Usuário removido com sucesso!"}, status=status.HTTP_200_OK)

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "data para verificar a disponibilidade"},
                },
                "required": ["date"]
            }
        },
        responses={200: {"description": "Lista de membros disponíveis da equipe"}},
    )
    @action(detail=True, methods=['post'])
    def get_available_members(self, request, pk=None):
        team = get_object_or_404(Team, pk=pk)
        date = request.data.get("date")
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()

        unavailable_members = team.members.filter(unavailability__start_date=date_obj).distinct()

        assigned_members = team.members.filter(schedules__schedule__date=date_obj).distinct()

        members = team.members.exclude(pk__in=unavailable_members)

        members = members.exclude(pk__in=assigned_members)
        
        
        return Response(
            {
                "available_members": members.values("id", "first_name"), 
                "unavailable_members": unavailable_members.values("id", "first_name"),
                "assigned_members": assigned_members.values("id", "first_name", "schedules__schedule__name", "schedules__schedule__team__name")
            }, 
            status=status.HTTP_200_OK)

        
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']
