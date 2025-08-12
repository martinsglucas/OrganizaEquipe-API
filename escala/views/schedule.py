from rest_framework.viewsets import ModelViewSet
from escala.models import Schedule
from escala.serializers import CreateScheduleSerializer, RetrieveScheduleSerializer

class ScheduleViewSet(ModelViewSet):
    queryset = Schedule.objects.all()
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return CreateScheduleSerializer
        if self.action in ['list', 'retrieve']:
            return RetrieveScheduleSerializer
        return super().get_serializer
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']