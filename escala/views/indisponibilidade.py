from rest_framework.viewsets import ModelViewSet
from escala.models import Indisponibilidade
from escala.serializers import IndisponibilidadeSerializer, CreateIndisponibilidadeSerializer
from datetime import datetime, timedelta
from django.db.models import Q

class IndisponibilidadeViewSet(ModelViewSet):
    queryset = Indisponibilidade.objects.all()
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        date = self.request.query_params.get('date', None)
        
        if user_only:
            queryset = queryset.filter(usuario=self.request.user)
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                first_day = date_obj.replace(day=1)
                last_day = (date_obj.replace(month=date_obj.month % 12 + 1, day=1) - timedelta(days=1))
                queryset = queryset.filter(
                    Q(data_inicio__gte=first_day , data_inicio__lte=last_day)
                )
            except ValueError:
                pass
        
        return queryset
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateIndisponibilidadeSerializer
        return IndisponibilidadeSerializer