from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.serializers import ModelSerializer, CharField, ValidationError, HiddenField, CurrentUserDefault, PrimaryKeyRelatedField, SerializerMethodField
from django.contrib.auth.models import User
from escala.models import Usuario, Funcao, Equipe, Escala, ParticipacaoEscala, Indisponibilidade
from django.contrib.auth import authenticate


class UsuarioSerializer(ModelSerializer):
    password = CharField(write_only=True, required=True)

    class Meta:
        model = Usuario
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'password']
        read_only_fields = ['is_active', 'is_staff', 'is_superuser']
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, data):
        if self.instance is None:
            if Usuario.objects.filter(email=data['email']).exists():
                raise ValidationError({'email': 'Já existe um usuário com este email.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Usuario(**validated_data)
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


class UsuarioMembroSerializer(ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'first_name', 'last_name', 'email']

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['user_id'] = user.id

        return token

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(username=email, password=password)
        
        if not user:
            raise ValidationError('Invalid email or password')
        
        data = super().validate(attrs)
        data['user_id'] = self.user.id

        return data

class FuncaoSerializer(ModelSerializer):
    class Meta:
        model = Funcao
        fields = '__all__'

class CreateIndisponibilidadeSerializer(ModelSerializer):
    usuario = HiddenField(default=CurrentUserDefault())
    class Meta:
        model = Indisponibilidade
        fields = ('usuario','descricao', 'data_inicio', 'data_fim')
    def create(self, validated_data):
        indisponibilidade = Indisponibilidade.objects.create(**validated_data)
        return indisponibilidade

class IndisponibilidadeSerializer(ModelSerializer):
    class Meta:
        model = Indisponibilidade
        fields = ('usuario','descricao', 'data_inicio', 'data_fim')

class CreateEquipeSerializer(ModelSerializer):
    codigo_de_acesso = CharField(read_only=True)
    class Meta:
        model = Equipe
        fields = ['id', 'nome', 'codigo_de_acesso']
    def create(self, validated_data):
        user = self.context['request'].user
        equipe = Equipe.objects.create(**validated_data)
        equipe.administradores.add(user)
        equipe.membros.add(user)
        return equipe

class RetrieveEquipeSerializer(ModelSerializer):
    administradores = UsuarioMembroSerializer(many=True)
    funcoes = FuncaoSerializer(many=True)
    membros = UsuarioMembroSerializer(many=True)
    class Meta:
        model = Equipe
        fields = ['id', 'nome', 'codigo_de_acesso', 'administradores', 'funcoes', 'membros']

class EquipeSerializer(ModelSerializer):
    administradores = PrimaryKeyRelatedField(queryset=Usuario.objects.all(), many=True)
    funcoes = PrimaryKeyRelatedField(queryset=Funcao.objects.all(), many=True)
    membros = PrimaryKeyRelatedField(queryset=Usuario.objects.all(), many=True)

    class Meta:
        model = Equipe
        fields = ['id', 'nome', 'codigo_de_acesso', 'administradores', 'funcoes', 'membros']
    def update(self, instance, validated_data):
        administradores_data = validated_data.pop('administradores', None)
        funcoes_data = validated_data.pop('funcoes', None)
        membros_data = validated_data.pop('membros', None)
        instance = super().update(instance, validated_data)
        if administradores_data is not None:
            instance.administradores.set(administradores_data)
        if funcoes_data is not None:
            instance.funcoes.set(funcoes_data)
        if membros_data is not None:
            instance.membros.set(membros_data)
        return instance


class CreateEscalaSerializer(ModelSerializer):
    participacoes = ParticipacaoEscalaSerializer(many=True)
    class Meta:
        model = Escala
        fields = '__all__'
    def validate(self, data):
        participacoes = data['participacoes']
        for participacao in participacoes:
            usuario = participacao['usuario']
            indisponibilidades = usuario.indisponibilidades.filter(data_inicio__lte=data['data'])
            if indisponibilidades.exists():
                raise ValidationError(f'O usuário {usuario} está indisponível nesta data.')
            # if ParticipacaoEscala.objects.filter(escala=data['escala'], usuario=data['usuario']).exists():
                # raise ValidationError('Este usuário já está participando desta escala.')
        return data
    def add_participacoes(self, escala, participacoes):
        for participacao in participacoes:
            funcoes_data = participacao.pop('funcoes')
            usuario_data = participacao.pop('usuario').id

            try:
                usuario = Usuario.objects.get(id=usuario_data)
            except Usuario.DoesNotExist:
                raise ValidationError(f"O usuario {usuario_data} não faz parte da equipe {escala.equipe.nome}.")

            participacao_escala = ParticipacaoEscala.objects.create(escala=escala, usuario=usuario)
            participacao_escala.funcoes.set(funcoes_data)
            participacao_escala.save()
    def create(self, validated_data):
        participacoes = validated_data.pop('participacoes')

        escala = Escala.objects.create(**validated_data)

        self.add_participacoes(escala, participacoes)

        return escala
    def update(self, instance, validated_data):
        participacoes_data = validated_data.pop('participacoes')
        instance = super().update(instance, validated_data)
        instance.participacoes.all().delete()
        self.add_participacoes(instance, participacoes_data)
        return instance
    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
    #     data['participacoes'] = ParticipacaoEscalaRetrieveSerializer(instance.participacoes.all(), many=True).data
    #     return data

class RetrieveEscalaSerializer(ModelSerializer):
    participacoes = ParticipacaoEscalaRetrieveSerializer(many=True)
    class Meta:
        model = Escala
        fields = '__all__'