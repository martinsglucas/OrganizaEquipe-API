from rest_framework.viewsets import ModelViewSet
from escala.models import ScheduleParticipation
from escala.serializers import ScheduleParticipationSerializer, RetrieveScheduleSerializer, UpdateScheduleParticipationSerializer

class ScheduleParticipationViewSet(ModelViewSet):
    queryset = ScheduleParticipation.objects.all()
    serializer_class = ScheduleParticipationSerializer
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RetrieveScheduleSerializer
        if self.action in ['update', 'partial_update']:
            return UpdateScheduleParticipationSerializer
        return ScheduleParticipationSerializer