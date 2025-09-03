from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.serializers import ModelSerializer, CharField, ValidationError, HiddenField, CurrentUserDefault, PrimaryKeyRelatedField, SerializerMethodField
from escala.models import User, Role, Team, Schedule, ScheduleParticipation, Unavailability, Organization, TeamInvitation, OrganizationInvitation, Request
from django.contrib.auth import authenticate

class UserSerializer(ModelSerializer):
    password = CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'password']
        read_only_fields = ['is_active', 'is_staff', 'is_superuser']
        extra_kwargs = {
            'email': {'required': True},
        }
    
    def validate(self, data):
        if self.instance is None:
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

class UserMemberSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        return token

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(username=email, password=password)
        
        if not user:
            raise ValidationError('Invalid email or password')
        
        data = super().validate(attrs)
        data['user'] = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        }

        return data

class RoleSerializer(ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class CreateUnavailabilitySerializer(ModelSerializer):
    user = HiddenField(default=CurrentUserDefault())
    
    class Meta:
        model = Unavailability
        fields = ('id','user','description', 'start_date', 'end_date')
    
    def create(self, validated_data):
        unavailability = Unavailability.objects.create(**validated_data)
        return unavailability

class UnavailabilitySerializer(ModelSerializer):
    class Meta:
        model = Unavailability
        fields = ('id','user','description', 'start_date', 'end_date')

class OrganizationInvitationSerializer(ModelSerializer):
    class Meta:
        model = OrganizationInvitation
        fields = '__all__'
    
    def validate(self, data):
        organization = Organization.objects.filter(id=data["organization"].id).first()
        user = User.objects.filter(email=data["recipient_email"]).first()

        if not organization:
            raise ValidationError({"organization": "Organização não encontrada."})
        if not user:
            raise ValidationError({"user": "Usuário não encontrado."})
        if user and organization.members.filter(id=user.id).exists():
            raise ValidationError({"recipient_email": f"{user.first_name} já faz parte dessa organização."})
        
        return data

class TeamInvitationSerializer(ModelSerializer):
    class Meta:
        model = TeamInvitation
        fields = '__all__'
    
    def validate(self, data):
        team = Team.objects.filter(id=data["team"].id).first()
        user = User.objects.filter(email=data["recipient_email"]).first()

        if not team:
            raise ValidationError({"team": "Equipe não encontrada."})
        if not user:
            raise ValidationError({"user": "Usuário não encontrado."})
        if user and team.members.filter(id=user.id).exists():
            raise ValidationError({"recipient_email": f"{user.first_name} já faz parte dessa equipe."})
        if user and not Organization.objects.filter(members__id=user.id).exists():
            raise ValidationError({"recipient_email": f"{user.first_name} não faz parte da organização."})
        
        return data

class CreateRequestSerializer(ModelSerializer):

    class Meta:
        model = Request
        fields = '__all__'

class RequestSerializer(ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Request
        fields = '__all__'

class RetrieveOrganizationSerializer(ModelSerializer):
    admins = UserMemberSerializer(many=True)
    members = UserMemberSerializer(many=True)
    invitations = OrganizationInvitationSerializer(many=True)
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'code_access', 'admins', 'members', 'invitations']

class OrganizationSerializer(ModelSerializer):
    admins = PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)
    members = PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'code_access', 'admins', 'members']
    
    def update(self, instance, validated_data):
        admins_data = validated_data.pop('admins', None)
        members_data = validated_data.pop('members', None)
        instance = super().update(instance, validated_data)
        if admins_data is not None:
            instance.admins.set(admins_data)
        if members_data is not None:
            instance.members.set(members_data)
        return instance
    
class RetrieveOrganizationInvitationSerializer(ModelSerializer):
    organization = RetrieveOrganizationSerializer()

    class Meta:
        model = OrganizationInvitation
        fields = '__all__'

class CreateTeamSerializer(ModelSerializer):
    code_access = CharField(read_only=True)
    admins = UserMemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = Team
        fields = ['id', 'name', 'code_access', 'organization', 'admins']
    
    def create(self, validated_data):
        user = self.context['request'].user
        team = Team.objects.create(**validated_data)
        team.admins.add(user)
        team.members.add(user)
        return team

class RetrieveTeamSerializer(ModelSerializer):
    admins = UserMemberSerializer(many=True)
    roles = RoleSerializer(many=True)
    members = UserMemberSerializer(many=True)
    invitations = TeamInvitationSerializer(many=True)
    
    class Meta:
        model = Team
        fields = ['id', 'name', 'code_access', 'admins', 'roles', 'members', 'organization', 'invitations']

class TeamSerializer(ModelSerializer):
    admins = PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)
    roles = PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True)
    members = PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)

    class Meta:
        model = Team
        fields = ['id', 'name', 'code_access', 'admins', 'roles', 'members']
    
    def update(self, instance, validated_data):
        admins_data = validated_data.pop('admins', None)
        roles_data = validated_data.pop('roles', None)
        members_data = validated_data.pop('members', None)
        instance = super().update(instance, validated_data)
        if admins_data is not None:
            instance.admins.set(admins_data)
        if roles_data is not None:
            instance.roles.set(roles_data)
        if members_data is not None:
            instance.members.set(members_data)
        return instance

class RetrieveTeamInvitationSerializer(ModelSerializer):
    team = RetrieveTeamSerializer()

    class Meta:
        model = TeamInvitation
        fields = '__all__'

class ScheduleParticipationSerializer(ModelSerializer):
    roles = PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True)
    user = PrimaryKeyRelatedField(queryset=User.objects.all())
    
    class Meta:
        model = ScheduleParticipation
        fields = ('id', 'roles','user')
    
    def create(self, validated_data):
        roles_data = validated_data.pop('roles')
        member_data = validated_data.pop('user')
        schedule_participation = ScheduleParticipation.objects.create(**validated_data)
        schedule_participation.roles.set(roles_data)
        schedule_participation.user = User.objects.get(user=member_data)
        schedule_participation.save()
        return schedule_participation

class RetrieveScheduleParticipationSerializer(ModelSerializer):
    roles = RoleSerializer(many=True)
    user = UserMemberSerializer()
    
    class Meta:
        model = ScheduleParticipation
        fields = ('id', 'roles','user', 'confirmation')

class UpdateScheduleParticipationSerializer(ModelSerializer):
    roles = PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True)
    
    class Meta:
        model = ScheduleParticipation
        fields = ('roles','confirmation')
    
    def update(self, instance, validated_data):
        roles_data = validated_data.pop('roles')
        instance = super().update(instance, validated_data)
        instance.roles.set(roles_data)
        return instance

class CreateScheduleSerializer(ModelSerializer):
    participations = ScheduleParticipationSerializer(many=True)
    
    class Meta:
        model = Schedule
        fields = '__all__'
    
    def validate(self, data):
        participations = data['participations']
        for participation in participations:
            user = participation['user']
            unavailability = user.unavailability.filter(start_date__lte=data['date'])
            # if unavailability.exists():
                # raise ValidationError(f'O usuário {user} está indisponível nesta data.')
            # if ParticipacaoEscala.objects.filter(escala=data['escala'], usuario=data['usuario']).exists():
                # raise ValidationError('Este usuário já está participando desta escala.')
        return data
    
    def add_participations(self, schedule, participations):
        for participation in participations:
            roles_data = participation.pop('roles')
            user_data = participation.pop('user').id

            try:
                user = User.objects.get(id=user_data)
            except User.DoesNotExist:
                raise ValidationError(f"O usuario {user_data} não faz parte da equipe {schedule.team.name}.")

            schedule_participation = ScheduleParticipation.objects.create(schedule=schedule, user=user)
            schedule_participation.roles.set(roles_data)
            schedule_participation.save()
    
    def create(self, validated_data):
        participations = validated_data.pop('participations')
        schedule = Schedule.objects.create(**validated_data)
        self.add_participations(schedule, participations)
        return schedule
    
    def update(self, instance, validated_data):
        participations_data = validated_data.pop('participations')
        instance = super().update(instance, validated_data)
        instance.participations.all().delete()
        self.add_participations(instance, participations_data)
        return instance
    
    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
    #     data['participacoes'] = ParticipacaoEscalaRetrieveSerializer(instance.participacoes.all(), many=True).data
    #     return data

class RetrieveScheduleSerializer(ModelSerializer):
    participations = RetrieveScheduleParticipationSerializer(many=True)
    team = RetrieveTeamSerializer()
    
    class Meta:
        model = Schedule
        fields = '__all__'
