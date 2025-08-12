from rest_framework.viewsets import ModelViewSet
from escala.models import Organization
from drf_spectacular.utils import extend_schema
from escala.serializers import OrganizationSerializer, RetrieveOrganizationSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class OrganizationViewSet(ModelViewSet):
    queryset = Organization.objects.all()
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        code_access = self.request.query_params.get('codeAccess', None)
        
        if user_only:
            queryset = queryset.filter(members=self.request.user)
        if code_access:
            queryset = queryset.filter(code_access=code_access)
        
        return queryset
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return OrganizationSerializer
        elif self.action in ['retrieve', 'list']:
            return RetrieveOrganizationSerializer
        return super().get_serializer_class()
    
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID do usuário a ser adicionado"}
                },
                "required": ["user_id"]
            }
        },
        responses={200: {"description": "Usuário adicionado com sucesso!"}},
    )
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        organization = get_object_or_404(Organization, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if organization.members.filter(id=user_id).exists():
            return Response({"message": "Usuário já faz parte da equipe."}, status=status.HTTP_200_OK)
        organization.members.add(user_id)
        organization.save()

        return Response({"message": "Usuário adicionado com sucesso!"}, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID do usuário a ser removido"}
                },
                "required": ["user_id"]
            }
        },
        responses={200: {"description": "Usuário removido com sucesso!"}},
    )
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        organization = get_object_or_404(Organization, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if not organization.members.filter(id=user_id).exists():
            return Response({"message": "Usuário não encontrado na equipe."}, status=status.HTTP_404_NOT_FOUND)
        organization.members.remove(user_id)
        if organization.admins.filter(id=user_id).exists():
            organization.admins.remove(user_id)
        organization.save()

        return Response({"message": "Usuário removido com sucesso!"}, status=status.HTTP_200_OK)
	# permission_classes = [AllowPostWithoutAuthentication]
	# http_method_names = ['get', 'post', 'put', 'delete']