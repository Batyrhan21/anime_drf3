import jwt
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import login as log, authenticate 
from rest_framework import response, status, generics, views, exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from config import settings
from .exceptions import UserNotVerified
from .utils import Util

from .models import User
from .serializers import (
                          UserSerializer,
                          RegistrationSerializer,
                          EmailVerificationSerializer,
                          LoginSerializer,
                          LoginResponseSerializer
                         )


def get_login_response(user, request):
    refresh = RefreshToken.for_user(user)
    data = {
        "user": UserSerializer(instance=user, context={'request': request}).data,
        "refresh": str(refresh),
        "access": str(refresh.access_token)
    }
    return data


class RegistrationAPIView(generics.GenericAPIView):
    serializer_class = RegistrationSerializer

    def post(self, request):
        serializers = self.serializer_class(data=request.data)
        serializers.is_valid(raise_exception=True)
        serializers.save()
        current_site = get_current_site(
        request=request).domain
        user_data = serializers.data
        user = User.objects.get(email=user_data['email'])
        token = RefreshToken.for_user(user).access_token
        abs_url = f'http://{current_site}/api/v1/users/verify-email/'+ '?token=' + str(token)
        email_body = f'Hello' \
                     f'Use this link to activate your email\n ' \
                     f'The link will be active for 10 minutes \n {abs_url}'
        data = {'email_body': email_body, 'to_email': user.email,
            'email_subject': 'Verify your email'}
        Util.send_email(data)
        return Response(user_data, status=status.HTTP_201_CREATED)


class ProfileAPIView(generics.GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(responses={'200': UserSerializer()}, tags=['auth'])
    def get(self, request):
        user = request.userexceptions,
        serializer = self.get_serializer(instance=request.user)
        return response.Response(data=serializer.data)

    def patch(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(data=serializer.data)
    
    def delete(self, request):
        request.user.delete()
        return response.Response(status.HTTP_200_OK)


class VerifyEmail(views.APIView):
    serializer_class = EmailVerificationSerializer

    token_param_config = openapi.Parameter(
        'token', in_=openapi.IN_QUERY, description='Description', type=openapi.TYPE_STRING)

    @swagger_auto_schema(manual_parameters=[token_param_config])
    def get(self, request):
        token = request.GET.get('token')

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms="HS256")
            user = User.objects.get(id=payload['user_id'])
            if not user.is_email_confirmed:
                user.is_email_confirmed = True
                user.is_active = True
                user.save()
            return Response({'email': 'Successfully activated'}, status=status.HTTP_200_OK)
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Activation Expired'}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.exceptions.DecodeError:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class LoginAPIView(generics.GenericAPIView):
    authentication_classes = ()
    permission_classes = ()
    serializer_class = LoginSerializer

    @swagger_auto_schema(responses={'200': LoginResponseSerializer()}, tags=['auth'])
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = authenticate(email=serializer.validated_data['email'], password=serializer.validated_data['password'])
        if not user:
            raise exceptions.AuthenticationFailed()
        log(request, user)
        if request.user.is_email_confirmed == False:
            raise UserNotVerified()
        return response.Response(data=get_login_response(user, request))
