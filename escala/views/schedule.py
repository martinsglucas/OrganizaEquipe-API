from rest_framework.viewsets import ModelViewSet
from escala.models import Schedule
from escala.serializers import CreateScheduleSerializer, RetrieveScheduleSerializer
from django.utils import timezone

class ScheduleViewSet(ModelViewSet):
    queryset = Schedule.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        filter = self.request.query_params.get('filter', 'all').lower()

        if user_only:
            queryset = (
                queryset.filter(
                    participations__user=self.request.user
                ) | queryset.filter(
                    team__admins=self.request.user
                )
            ).distinct()

        timezone.activate('America/Sao_Paulo')
        # local_time = timezone.localtime(timezone.now()).time()
        local_date = timezone.localtime(timezone.now()).date()
        
        match (filter):
            case 'next':
                queryset = queryset.filter(date__gte=local_date)
                return queryset.order_by('date', 'hour')
            case 'past':
                queryset = queryset.filter(date__lt=local_date)
                return queryset.order_by('-date', '-hour')
            case _:
                return queryset

    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return CreateScheduleSerializer
        if self.action in ['list', 'retrieve']:
            return RetrieveScheduleSerializer
        return super().get_serializer
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']