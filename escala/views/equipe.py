from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter
from escala.models import Equipe
from escala.serializers import CreateEquipeSerializer, EquipeSerializer, RetrieveEquipeSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class EquipeViewSet(ModelViewSet):
    queryset = Equipe.objects.all()
    def get_queryset(self):
        queryset = super().get_queryset()
        user_only = self.request.query_params.get('userOnly', 'false').lower() == 'true'
        codigo_equipe = self.request.query_params.get('codeAccess', None)
        
        if user_only:
            queryset = queryset.filter(membros=self.request.user)
        if codigo_equipe:
            queryset = queryset.filter(codigo_de_acesso=codigo_equipe)
        
        return queryset
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateEquipeSerializer
        elif self.action in ['update', 'partial_update', 'list', 'destroy']:
            return EquipeSerializer
        elif self.action == 'retrieve':
            return RetrieveEquipeSerializer
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
        equipe = get_object_or_404(Equipe, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if equipe.membros.filter(id=user_id).exists():
            return Response({"message": "Usuário já faz parte da equipe."}, status=status.HTTP_200_OK)
        equipe.membros.add(user_id)
        equipe.save()

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
        equipe = get_object_or_404(Equipe, pk=pk)
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "O campo 'user_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if not equipe.membros.filter(id=user_id).exists():
            return Response({"message": "Usuário não encontrado na equipe."}, status=status.HTTP_404_NOT_FOUND)
        equipe.membros.remove(user_id)
        if equipe.administradores.filter(id=user_id).exists():
            equipe.administradores.remove(user_id)
        equipe.save()

        return Response({"message": "Usuário removido com sucesso!"}, status=status.HTTP_200_OK)
        
    # permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']