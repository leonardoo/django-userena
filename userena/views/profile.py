from django.core.exceptions import PermissionDenied
from django.views.generic import DetailView

from userena.utils import (get_user_model, get_user_profile)
from userena import settings as userena_settings


class ProfileDetailView(DetailView):

    """
    Detailed view of an user.

    :param username:
        String of the username of which the profile should be viewed.

    :param template_name:
        String representing the template name that should be used to display
        the profile.

    :param extra_context:
        Dictionary of variables which should be supplied to the template. The
        ``profile`` key is always the current profile.

    **Context**

    ``profile``
        Instance of the currently viewed ``Profile``.

    """

    model = get_user_model()
    slug_url_kwarg = 'username'
    slug_field = "username__iexact"
    template_name = userena_settings.USERENA_PROFILE_DETAIL_TEMPLATE
    context_object_name = "profile"
    extra_context = {
        'hide_email': userena_settings.USERENA_HIDE_EMAIL
    }

    def get_context_data(self, *args, **kwargs):
        context = super(ProfileDetailView, self).get_context_data(*args, **kwargs)
        if self.extra_context:
            context.update(self.extra_context)
        return context

    def get_object(self, queryset=None):
        obj = super(ProfileDetailView, self).get_object()
        profile = get_user_profile(user=obj)
        if not profile.can_view_profile(self.request.user):
            raise PermissionDenied
        return profile
