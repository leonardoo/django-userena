from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.generic import DetailView, ListView, UpdateView

from guardian.decorators import permission_required_or_403

from userena.decorators import secure_required
from userena.forms import EditProfileForm
from userena.utils import (get_profile_model, get_user_model, get_user_profile)
from userena import signals as userena_signals
from userena import settings as userena_settings

from .mixins import ExtraContextMixin


PROFILE_TEMPLATE = userena_settings.USERENA_PROFILE_DETAIL_TEMPLATE


class ProfileDetailView(ExtraContextMixin, DetailView):

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

    context_object_name = "profile"
    extra_context = {'hide_email': userena_settings.USERENA_HIDE_EMAIL}
    model = get_user_model()
    template_name = PROFILE_TEMPLATE
    slug_url_kwarg = 'username'
    slug_field = "username__iexact"

    def get_object(self, queryset=None):
        obj = super(ProfileDetailView, self).get_object()
        profile = get_user_profile(user=obj)
        if not profile.can_view_profile(self.request.user):
            raise PermissionDenied
        return profile


class ProfileEditView(ExtraContextMixin, UpdateView):

    """
    Edit profile.

    Edits a profile selected by the supplied username. First checks
    permissions if the user is allowed to edit this profile, if denied will
    show a 404. When the profile is successfully edited will redirect to
    ``success_url``.

    :param username:
        Username of the user which profile should be edited.

    :param form_class:

        Form that is used to edit the profile. The :func:`EditProfileForm.save`
        method of this form will be called when the form
        :func:`EditProfileForm.is_valid`.  Defaults to :class:`EditProfileForm`
        from userena.

    :param template_name:
        String of the template that is used to render this view. Defaults to
        ``userena/edit_profile_form.html``.

    :param success_url:
        Named URL which will be passed on to a django ``reverse`` function after
        the form is successfully saved. Defaults to the ``userena_detail`` url.

    :param extra_context:
        Dictionary containing variables that are passed on to the
        ``template_name`` template.  ``form`` key will always be the form used
        to edit the profile, and the ``profile`` key is always the edited
        profile.

    **Context**

    ``form``
        Form that is used to alter the profile.

    ``profile``
        Instance of the ``Profile`` that is edited.

    """

    form_class = EditProfileForm
    model = get_user_model()
    slug_url_kwarg = 'username'
    slug_field = "username__iexact"
    success_url = None
    template_name = 'userena/profile_form.html'
    extra_context = None

    @method_decorator(secure_required)
    @method_decorator(permission_required_or_403('change_profile', (get_profile_model(), 'user__username', 'username')))
    def dispatch(self, request, *args, **kwargs):
        return super(ProfileEditView, self).dispatch(request, *args, **kwargs)

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super(ProfileEditView, self).get_initial()
        initial.update({'first_name': self._user.first_name, 'last_name': self._user.last_name})
        return initial

    def get_object(self, queryset=None):
        obj = super(ProfileEditView, self).get_object()
        profile = get_user_profile(user=obj)
        self._user = obj
        return profile

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.success_url:
            # Send a signal that the profile has changed
            userena_signals.profile_change.send(sender=None, user=self._user)
            return self.success_url
        else:
            return reverse('userena_profile_detail', kwargs={'username': self._user.username})

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        form_valid = super(ProfileEditView, self).form_valid(form)
        if userena_settings.USERENA_USE_MESSAGES:
            messages.success(self.request, _('Your profile has been updated.'), fail_silently=True)
        return form_valid


class ProfileListView(ExtraContextMixin, ListView):
    """ Lists all profiles """
    context_object_name = 'profile_list'
    paginate_by = 50
    template_name = userena_settings.USERENA_PROFILE_LIST_TEMPLATE

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        if userena_settings.USERENA_DISABLE_PROFILE_LIST and not self.request.user.is_staff:
            raise Http404
        context = super(ProfileListView, self).get_context_data(**kwargs)
        return context

    def get_queryset(self):
        model = get_profile_model()
        queryset = model.objects.get_visible_profiles(self.request.user)
        queryset = queryset.select_related()
        return queryset


def profile_detail(request,
                   template_name=PROFILE_TEMPLATE,
                   extra_context=None,
                   url_field='username',
                   field_method="iexact",
                   **kwargs):
    """
    Detailed view of an user.

    :param template_name:
        String representing the template name that should be used to display
        the profile.

    :param extra_context:
        Dictionary of variables which should be supplied to the template. The
        ``profile`` key is always the current profile.

    :param url_field:
        Field in model for view search the profile.

    :param url_field:
        String that indicate the method for search in the model, must be exact,
        like iexact, and must be a QuerySet method.

    **Context**

    ``profile``
        Instance of the currently viewed ``Profile``.
    """

    slug_field = "{0}__{1}".format(url_field, field_method)
    return ProfileDetailView.as_view(template_name=template_name,
                                     extra_context=extra_context,
                                     slug_url_kwarg=url_field,
                                     slug_field=slug_field)(request, **kwargs)
