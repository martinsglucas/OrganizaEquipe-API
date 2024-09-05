from rest_framework.serializers import ModelSerializer, CharField, ValidationError
from django.contrib.auth.models import User

class UsuarioSerializer(ModelSerializer):
    password = CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'password']
        read_only_fields = ['is_active', 'is_staff', 'is_superuser']
        extra_kwargs = {
            'username': {'required': True},
            'email': {'required': True},
        }
    
    def validate(self, data):
        if self.instance is None:
            if User.objects.filter(username=data['username']).exists():
                raise ValidationError({'username': 'Já existe um usuário com este username.'})
            if User.objects.filter(email=data['email']).exists():
                raise ValidationError({'email': 'Já existe um usuário com este email.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance