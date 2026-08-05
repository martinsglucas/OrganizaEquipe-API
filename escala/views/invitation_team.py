from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from escala.models import Team, TeamInvitation
from escala.serializers import TeamInvitationSerializer, RetrieveTeamInvitationSerializer


class TeamInvitationViewSet(ModelViewSet):
    queryset = TeamInvitation.objects.select_related("team", "team__organization")
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return RetrieveTeamInvitationSerializer
        return TeamInvitationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if self.action == "list":
            return queryset.filter(recipient_email__iexact=user.email)
        if self.action == "retrieve":
            return queryset.filter(
                Q(recipient_email__iexact=user.email) | Q(team__admins=user)
            ).distinct()
        return queryset

    def create(self, request, *args, **kwargs):
        team = Team.objects.filter(pk=request.data.get("team")).first()
        if team:
            self._require_target_admin(team, request.user)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        team = serializer.validated_data["team"]
        self._require_target_admin(team, self.request.user)
        serializer.save(sender_name=self.request.user.first_name)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        with transaction.atomic():
            invitation = self._get_recipient_invitation(pk, lock=True)
            if not invitation.team.organization.members.filter(id=request.user.id).exists():
                raise PermissionDenied(
                    "Você precisa pertencer à organização antes de aceitar este convite."
                )
            invitation.team.members.add(request.user)
            invitation.delete()
        return Response({"message": "Convite aceito com sucesso!"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        with transaction.atomic():
            invitation = self._get_recipient_invitation(pk, lock=True)
            invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        with transaction.atomic():
            invitation = get_object_or_404(
                TeamInvitation.objects.select_for_update().select_related("team"),
                pk=pk,
            )
            self._require_target_admin(invitation.team, request.user)
            invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_recipient_invitation(self, pk, lock=False):
        queryset = TeamInvitation.objects.select_related(
            "team",
            "team__organization",
        )
        if lock:
            queryset = queryset.select_for_update()
        return get_object_or_404(
            queryset,
            pk=pk,
            recipient_email__iexact=self.request.user.email,
        )

    @staticmethod
    def _require_target_admin(team, user):
        if not team.admins.filter(id=user.id).exists():
            raise PermissionDenied("Apenas admins da equipe podem gerenciar convites.")
