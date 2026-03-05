from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from escala.serializers import CustomTokenObtainPairSerializer
from django.conf import settings


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login: retorna o access token no body e seta o refresh token
    como cookie HttpOnly — inacessível via JavaScript.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        data = serializer.validated_data
        refresh_token = data.pop("refresh")

        response = Response(data, status=status.HTTP_200_OK)

        response.set_cookie(
            key="refreshToken",
            value=refresh_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="None",
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path="/api/token/",
        )

        return response


class CookieTokenRefreshView(APIView):
    """
    Refresh: lê o refresh token do cookie HttpOnly e retorna um novo access token.
    Não exige autenticação prévia.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refreshToken")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token não encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            token = RefreshToken(refresh_token)
            access_token = str(token.access_token)
        except TokenError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"access": access_token}, status=status.HTTP_200_OK)

        new_refresh = str(token)
        response.set_cookie(
            key="refreshToken",
            value=new_refresh,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="None",
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path="/api/token/",
        )

        return response


class LogoutView(APIView):
    """
    Logout: invalida o cookie do refresh token.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = Response(
            {"detail": "Logout realizado com sucesso."},
            status=status.HTTP_200_OK,
        )
        response.delete_cookie(
            key="refreshToken",
            path="/api/token/",
        )
        return response