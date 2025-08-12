from rest_framework.viewsets import ModelViewSet
from escala.models import User
from escala.serializers import UserSerializer
from escala.permissions import AllowPostWithoutAuthentication

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowPostWithoutAuthentication]
    # http_method_names = ['get', 'post', 'put', 'delete']