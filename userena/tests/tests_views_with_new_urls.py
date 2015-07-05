import re

from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.core import mail
from django.contrib.auth.forms import PasswordChangeForm
from django.test import TestCase

try:
    from django.test import override_settings
except Exception, e:
    from django.test.utils import override_settings

from userena import forms
from userena import settings as userena_settings
from userena.utils import get_user_model, get_user_profile

User = get_user_model()


@override_settings(ROOT_URLCONF='urls_change')
class UserenaViewsTests(TestCase):
    """ Test the account views """
    fixtures = ['users', 'profiles']

    def test_profile_detail_view(self):
        """ A ``GET`` to the detailed view of a user """
        response = self.client.get(reverse('userena_profile_detail',
                                           kwargs={'username': 'john'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'userena/profile_detail.html')
