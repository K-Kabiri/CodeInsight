from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ObtainTokenView(ObtainAuthToken):
    """
    POST username + password -> an authentication token.

    Valid credentials create (or reuse) the user's token and return it;
    invalid credentials are rejected with a 400 and no token is issued.
    """

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class MeView(APIView):
    """
    Identity of the authenticated user.

    Exists so clients can confirm which user a token belongs to; it is
    also the first protected endpoint, establishing the 401 contract
    that every owner-scoped resource later relies on.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
            }
        )
