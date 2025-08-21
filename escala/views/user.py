from rest_framework.viewsets import ModelViewSet
from escala.models import User
from escala.serializers import UserSerializer
from escala.permissions import AllowPostWithoutAuthentication
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']
    
    @extend_schema(
        responses={200: {"description": "transformar usuário em superuser"}},
    )
    @action(detail=True, methods=['get'])
    def turn_superuser(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.is_staff = True
        user.is_superuser = True
        return Response({"message": "Usuário adicionado com sucesso!"}, status=status.HTTP_200_OK)