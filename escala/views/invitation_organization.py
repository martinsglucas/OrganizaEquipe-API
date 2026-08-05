from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from escala.models import Organization, OrganizationInvitation
from escala.serializers import (
    OrganizationInvitationSerializer,
    RetrieveOrganizationInvitationSerializer,
)


class OrganizationInvitationViewSet(ModelViewSet):
    queryset = OrganizationInvitation.objects.select_related("organization")
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return RetrieveOrganizationInvitationSerializer
        return OrganizationInvitationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if self.action == "list":
            return queryset.filter(recipient_email__iexact=user.email)
        if self.action == "retrieve":
            return queryset.filter(
                Q(recipient_email__iexact=user.email)
                | Q(organization__admins=user)
            ).distinct()
        return queryset

    def create(self, request, *args, **kwargs):
        organization = Organization.objects.filter(
            pk=request.data.get("organization")
        ).first()
        if organization:
            self._require_target_admin(organization, request.user)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        self._require_target_admin(organization, self.request.user)
        serializer.save(sender_name=self.request.user.first_name)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        with transaction.atomic():
            invitation = self._get_recipient_invitation(pk, lock=True)
            invitation.organization.members.add(request.user)
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
                OrganizationInvitation.objects.select_for_update().select_related(
                    "organization"
                ),
                pk=pk,
            )
            self._require_target_admin(invitation.organization, request.user)
            invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_recipient_invitation(self, pk, lock=False):
        queryset = OrganizationInvitation.objects.select_related("organization")
        if lock:
            queryset = queryset.select_for_update()
        return get_object_or_404(
            queryset,
            pk=pk,
            recipient_email__iexact=self.request.user.email,
        )

    @staticmethod
    def _require_target_admin(organization, user):
        if not organization.admins.filter(id=user.id).exists():
            raise PermissionDenied(
                "Apenas admins da organização podem gerenciar convites."
            )
