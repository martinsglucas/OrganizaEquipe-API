from rest_framework.viewsets import ModelViewSet
from escala.models import Organizacao
from escala.serializers import OrganizacaoSerializer

class OrganizacaoViewSet(ModelViewSet):
    queryset = Organizacao.objects.all()
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        
        if user_only:
            queryset = queryset.filter(membros=self.request.user)
        
        return queryset
    serializer_class = OrganizacaoSerializer
	# permission_classes = [AllowPostWithoutAuthentication]
	# http_method_names = ['get', 'post', 'put', 'delete']