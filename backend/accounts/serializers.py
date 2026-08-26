from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """
    Sign-up payload: a username and a password.

    Username rules come from the User model itself (the same
    UnicodeUsernameValidator and 150-char limit the model enforces);
    the duplicate check runs here so a repeated username is rejected
    with a clear message instead of surfacing as an IntegrityError.
    The password must satisfy the project's configured
    AUTH_PASSWORD_VALIDATORS, exactly as Django's own user forms do.
    """

    username = serializers.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    password = serializers.CharField(
        max_length=128,
        write_only=True,
        trim_whitespace=False,
    )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with that username already exists."
            )
        return value

    def validate(self, attrs):
        try:
            validate_password(
                attrs["password"],
                user=User(username=attrs["username"]),
            )
        except DjangoValidationError as exc:
            # Surface the validator messages on the password field so
            # the client can render them next to the input.
            raise serializers.ValidationError(
                {"password": exc.messages}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
