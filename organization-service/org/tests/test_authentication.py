from django.test import SimpleTestCase
from rest_framework_simplejwt.tokens import AccessToken

from org.authentication import ServiceJWTAuthentication


class ServiceJWTAuthenticationTests(SimpleTestCase):
    def test_sub_and_roles_claims_are_used_for_identity_mapping(self):
        token = AccessToken()
        token["sub"] = "123e4567-e89b-12d3-a456-426614174000"
        token["roles"] = ["admin"]

        user = ServiceJWTAuthentication().get_user(token)

        self.assertTrue(user.is_authenticated)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(str(user.id), "123e4567-e89b-12d3-a456-426614174000")
