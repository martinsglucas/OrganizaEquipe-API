from django.db.models import Q
from rest_framework.viewsets import ModelViewSet

from escala.models import ScheduleParticipation
from escala.permissions import IsParticipationAccessible
from escala.serializers import (
    RetrieveScheduleSerializer,
    ScheduleParticipationSerializer,
    UpdateScheduleParticipationSerializer,
)


class ScheduleParticipationViewSet(ModelViewSet):
    queryset = ScheduleParticipation.objects.all()
    serializer_class = ScheduleParticipationSerializer
    permission_classes = [IsParticipationAccessible]

    def get_queryset(self):
        user = self.request.user
        return super().get_queryset().filter(
            Q(schedule__team__members=user) | Q(schedule__team__admins=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RetrieveScheduleSerializer
        if self.action in ['update', 'partial_update']:
            return UpdateScheduleParticipationSerializer
        return ScheduleParticipationSerializer
