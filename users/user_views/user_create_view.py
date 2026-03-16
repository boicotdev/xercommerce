from rest_framework.generics import CreateAPIView
from users.users_serializers.user_serializer import UserSerializer
from users.services.user_service import create_user


class UserCreateView(CreateAPIView):
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        create_user(serializer)
