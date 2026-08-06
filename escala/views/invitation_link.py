from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from escala.models import (
    InvitationLink,
    Organization,
    Team,
    generate_invitation_link_token,
)
from escala.serializers import (
    InvitationLinkInputSerializer,
    InvitationLinkExpirationSerializer,
    InvitationLinkSerializer,
    PublicInvitationLinkSerializer,
)


class InvitationLinkViewSet(GenericViewSet):
    queryset = InvitationLink.objects.select_related('organization', 'team')
    serializer_class = InvitationLinkSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'resolve':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return super().get_queryset().none()

        queryset = super().get_queryset().filter(
            Q(organization__admins=user) | Q(team__admins=user)
        ).distinct()
        target_type = self.request.query_params.get('target_type')
        target_id = self.request.query_params.get('target_id')
        if target_type == 'organization':
            queryset = queryset.filter(organization_id=target_id)
        elif target_type == 'team':
            queryset = queryset.filter(team_id=target_id)
        return queryset

    def list(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    @transaction.atomic
    def create(self, request):
        input_serializer = InvitationLinkInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        target_type = input_serializer.validated_data['target_type']
        target_id = input_serializer.validated_data['target_id']
        target = self._get_target(target_type, target_id)
        self._require_target_admin(target, target_type, request.user)

        lookup = {target_type: target}
        link = InvitationLink.objects.select_for_update().filter(**lookup).first()
        if link and link.is_active:
            return Response(self.get_serializer(link).data, status=status.HTTP_200_OK)

        expires_at = input_serializer.validated_data.get('expires_at')
        if link:
            link.token = generate_invitation_link_token()
            link.created_by = request.user
            link.expires_at = expires_at
            link.revoked_at = None
            link.save()
        else:
            link = InvitationLink.objects.create(
                **lookup,
                created_by=request.user,
                expires_at=expires_at,
            )
        return Response(self.get_serializer(link).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        with transaction.atomic():
            link = self._get_managed_link(pk, request.user)
            if link is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            link.revoked_at = timezone.now()
            link.save(update_fields=['revoked_at', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        expires_serializer = InvitationLinkExpirationSerializer(data=request.data)
        expires_serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            link = self._get_managed_link(pk, request.user)
            if link is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            link.token = generate_invitation_link_token()
            link.created_by = request.user
            link.expires_at = expires_serializer.validated_data.get('expires_at')
            link.revoked_at = None
            link.save()
        return Response(self.get_serializer(link).data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def resolve(self, request):
        token = request.query_params.get('token')
        link = get_object_or_404(
            InvitationLink.objects.select_related('organization', 'team'),
            token=token,
            revoked_at__isnull=True,
        )
        if not link.is_active:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PublicInvitationLinkSerializer(link).data)

    @action(detail=False, methods=['post'])
    def accept(self, request):
        with transaction.atomic():
            link = InvitationLink.objects.select_for_update().filter(
                token=request.data.get('token'),
                organization__isnull=False,
                revoked_at__isnull=True,
            ).first()
            if link is None or not link.is_active:
                return Response(status=status.HTTP_404_NOT_FOUND)
            link.organization.members.add(request.user)
        return Response(PublicInvitationLinkSerializer(link).data)

    @staticmethod
    def _get_target(target_type, target_id):
        model = Organization if target_type == 'organization' else Team
        return get_object_or_404(model.objects.select_for_update(), pk=target_id)

    @staticmethod
    def _require_target_admin(target, target_type, user):
        if not target.admins.filter(id=user.id).exists():
            target_label = 'organização' if target_type == 'organization' else 'equipe'
            raise PermissionDenied(
                f'Apenas admins da {target_label} podem gerenciar links de convite.'
            )

    @staticmethod
    def _get_managed_link(pk, user):
        link = InvitationLink.objects.select_for_update().filter(pk=pk).first()
        if link is None or not link.target.admins.filter(id=user.id).exists():
            return None
        return link
