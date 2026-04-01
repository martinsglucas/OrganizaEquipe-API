from rest_framework.permissions import BasePermission, SAFE_METHODS

from escala.models import Team


class AllowPostWithoutAuthentication(BasePermission):
    """
    Permite acesso não autenticado apenas para o método POST.
    """

    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return request.user and request.user.is_authenticated



def _is_team_member(user, team):
    return team.members.filter(id=user.id).exists() or team.admins.filter(id=user.id).exists()



def _is_team_admin(user, team):
    return team.admins.filter(id=user.id).exists()


class IsScheduleAccessible(BasePermission):
    message = "Você não tem permissão para acessar esta escala."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if view.action == "create":
            team_id = request.data.get("team")
            if not team_id:
                return True

            team = Team.objects.filter(pk=team_id).first()
            if not team:
                return True

            return _is_team_admin(user, team)

        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return _is_team_member(request.user, obj.team)

        return _is_team_admin(request.user, obj.team)


class IsParticipationAccessible(BasePermission):
    message = "Você não tem permissão para acessar esta participação."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return _is_team_member(request.user, obj.schedule.team)

        return obj.user_id == request.user.id or _is_team_admin(request.user, obj.schedule.team)
