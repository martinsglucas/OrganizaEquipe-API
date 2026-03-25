from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from escala.models import PushSubscription
from escala.serializers import PushSubscriptionSerializer


class PushSubscriptionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = PushSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushSubscription.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        output = self.get_serializer(subscription)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def deactivate(self, request):
        token = request.data.get('token')

        if not token:
            return Response(
                {'error': "O campo 'token' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = PushSubscription.objects.filter(token=token).update(is_active=False)

        if not updated:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response({'message': 'Inscrição desativada com sucesso!'}, status=status.HTTP_200_OK)
