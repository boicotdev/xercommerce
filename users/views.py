import datetime
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from rest_framework import status, generics
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView, Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.utils.profile import create_user_profile_settings
from .models import User, UserProfileSettings
from .permissions import IsOwnerOrSuperUserPermission, IsOwnerOfProfileSettings
from utils.email_async import send_email_async
from users.services.handle_excel_file import ExcelUserParser, UsersBulkCreate
from .serializers import (
    AdminDashboardSerializer,
    UserSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    NewsletterSubscriptionSerializer,
    UserProfileSettingsSerializer,
    UploadUsersFileSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshPairView(TokenRefreshView):
    pass


class UserCreateAPIView(APIView):
    """
    Create a new `User` instance without any special permissions
    Any user can use this view to create an account
    """

    parser_classes = [MultiPartParser, JSONParser, FormParser]

    def post(self, request):
        required_fields = {"dni", "username", "email"}

        data = request.data
        missing_fields = required_fields - data.keys()

        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check if a User with the referral_code exists
        if request.data.get("referral_code"):
            try:
                User.objects.get(referral_code=request.data.get("referral_code"))
            except User.DoesNotExist:
                return Response(
                    {"error": "User with referral_code not found!"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # check if user with some required fields already exists.
        for field in required_fields:
            value = data.get(field)
            if value and User.objects.filter(**{field: value}).exists():
                return Response(
                    {"error": f'A user with {field} "{value}" already exists.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            context = {
                "user": request.data.get("first_name"),
                "subscriber_name": request.data.get("email"),
                "site_url": settings.SITE_URL,
                "site_name": settings.SITE_NAME,
                "year": datetime.datetime.now().year,
            }

            # handle user profile settings
            create_user_profile_settings(request.data.get("dni"))
            client_html = render_to_string("email/welcome-email.html", context)
            client_text = strip_tags(client_html)
            send_email_async(
                f'Bienvenido a {settings.SITE_NAME}',
                client_text,
                client_html,
                request.data.get('email')
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            token = RefreshToken(refresh_token)
            token.blacklist()  # Invalidar el token de refresh (requiere que el blacklisting esté habilitado)
            return Response(
                {"message": "Sesión cerrada exitosamente."}, status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"message": "Token no válido."}, status=status.HTTP_400_BAD_REQUEST
            )


# retrieve the basic data of the current administrator
class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        user_serializer = AdminDashboardSerializer(request.user)
        return Response(
            {
                "data": user_serializer.data,
            }
        )


class UserDashboardAPIView(APIView):
    """
    Create a new `User` instance without any special permissions
    Any user can use this view to create an account
    """

    parser_classes = [MultiPartParser, JSONParser, FormParser]
    permission_classes = [IsAdminUser]

    def post(self, request):
        required_fields = {"dni", "username", "email"}

        data = request.data
        missing_fields = required_fields - data.keys()

        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check if a User with the referral_code exists
        if request.data.get("referral_code"):
            try:
                User.objects.get(referral_code=request.data.get("referral_code"))
            except User.DoesNotExist:
                return Response(
                    {"error": "User with referral_code not found!"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # check if user with some required fields already exists.
        for field in required_fields:
            value = data.get(field)
            if value and User.objects.filter(**{field: value}).exists():
                return Response(
                    {"error": f'A user with {field} "{value}" already exists.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            context = {
                "user": request.data.get("first_name"),
                "subscriber_name": request.data.get("email"),
                "site_url": settings.SITE_URL,
                "site_name": settings.SITE_NAME,
                "year": datetime.datetime.now().year,
            }

            # handle user profile settings
            create_user_profile_settings(request.data.get("dni"))
            client_html = render_to_string("email/welcome-email.html", context)
            client_text = strip_tags(client_html)
            send_email_async(
                f'Bienvenido a {settings.SITE_NAME}',
                client_text,
                client_html,
                request.data.get('email')
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, dni):
        try:
            user = get_object_or_404(User, pk=dni)
            user.delete()
            return Response(
                {"message": "User was deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# retrieve user
class UserDetailsView(APIView):
    permission_classes = [IsOwnerOrSuperUserPermission]

    def get(self, request):
        user_id = request.query_params.get("user", None)
        if not user_id:
            return Response(
                {"message": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user = User.objects.get(pk=user_id)
            serializer = UserSerializer(user, many=False)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"message": f"User with ID {user_id} was'nt found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class ClientUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            queryset = User.objects.filter(role="customer")
            paginator = LimitOffsetPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = UserSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserUpdateView(APIView):

    """
    API view to update a single User instance.
    - You must provide the `dni` of the user to be updated in the payload.
    - Accepts multipart/form-data for file uploads (e.g., avatar).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request):
        def flatten_data(data):
            return {
                key: value[0] if isinstance(value, list) else value
                for key, value in data.items()
            }

        raw_data = request.data

        data = flatten_data(raw_data)

        dni = data.get("id")
        if not dni:
            return Response(
                {"message": "Falta el campo dni"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_instance = User.objects.get(dni=dni)

            serializer = UserSerializer(user_instance, data=data, partial=True)
            if serializer.is_valid():
                updated_user = serializer.save()
                return Response(
                    UserSerializer(updated_user).data, status=status.HTTP_200_OK
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response(
                {"message": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        except Exception:
            return Response(
                {"message": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# remove a single user
class UserDeleteView(APIView):
    """
    View created to handle `User` deletions
    -params: username.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        dni = request.user.dni
        if not dni:
            return Response(
                {"message": "User DNI field is required!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(dni=dni)
            user.delete()
            return Response(
                {"message": "User was deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.update_password(request.user)
            return Response(
                {"message": "Contraseña actualizada correctamente."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NewsletterSubscriptionView(APIView):
    """
    Endpoint para manejar la suscripción al boletín de nuevo suscriptor.
    Envía un correo de bienvenida al nuevo suscriptor.
    """

    def post(self, request):
        email = request.data.get("email")

        serializer = NewsletterSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Preparar y enviar el correo
        subject = "¡Gracias por suscribirte a nuestro boletín!"
        email = serializer.validated_data.pop('email')
        context = {
            "subscriber_name": email,
            "site_url": settings.SITE_URL,
            "site_name": settings.SITE_NAME,
            "year": datetime.datetime.now().year,
        }

        html_content = render_to_string("email/newsletter-subscription.html", context)
        text_content = strip_tags(html_content)
        send_email_async(
            subject,
            text_content,
            html_content,
            email
        )

        return Response({'message': 'Thanks for subscribing into our newsletter!'}, status=status.HTTP_201_CREATED)



class UserProfileSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOfProfileSettings]

    def get_object(self, pk):
        instance = get_object_or_404(UserProfileSettings, user__dni=pk)
        return instance

    def get(self, request):
        pk = request.user.dni
        profile = self.get_object(pk)
        self.check_object_permissions(profile, request)
        return Response(UserProfileSettingsSerializer(profile).data)

    def patch(self, request):
        pk = request.user.dni
        profile = self.get_object(pk)
        self.check_object_permissions(profile, request)
        serializer = UserProfileSettingsSerializer(
            profile, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserUploadFileAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = UploadUsersFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = request.data.get("file")

        # lets to create a user by any register inside the xlsx file

        service = ExcelUserParser()
        result = service.parse(file)
        response = UsersBulkCreate.execute(result)
        return Response(response, status=status.HTTP_201_CREATED)
