from django.contrib.auth.forms import PasswordChangeForm
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView

from guardian.decorators import permission_required_or_403

from userena.decorators import secure_required
from userena.utils import (get_user_model)
from userena import signals as userena_signals

from .mixins import ExtraContextMixin


class PasswordChangeView(ExtraContextMixin, UpdateView):

    """ Change password of user.

    This view is almost a mirror of the view supplied in
    :func:`contrib.auth.views.password_change`, with the minor change that in
    this view we also use the username to change the password. This was needed
    to keep our URLs logical (and REST) across the entire application. And
    that in a later stadium administrators can also change the users password
    through the web application itself.

    :param username:
        String supplying the username of the user who's password is about to be
        changed.

    :param template_name:
        String of the name of the template that is used to display the password
        change form. Defaults to ``userena/password_form.html``.

    :param class_form:
        Form used to change password. Default is the form supplied by Django
        itself named ``PasswordChangeForm``.

    :param success_url:
        Named URL that is passed onto a :func:`reverse` function with
        ``username`` of the active user. Defaults to the
        ``userena_password_complete`` URL.

    :param extra_context:
        Dictionary of extra variables that are passed on to the template. The
        ``form`` key is always used by the form supplied by ``pass_form``.

    **Context**

    ``form``
        Form used to change the password.

    """

    model = get_user_model()
    form_class = PasswordChangeForm
    slug_url_kwarg = 'username'
    slug_field = "username__iexact"
    success_url = None
    template_name = 'userena/password_form.html'

    @method_decorator(secure_required)
    @method_decorator(permission_required_or_403('change_user', (get_user_model(), 'username', 'username')))
    def dispatch(self, request, *args, **kwargs):
        return super(PasswordChangeView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super(PasswordChangeView, self).get_form_kwargs()
        if hasattr(self, 'object'):
            self._user = kwargs.pop("instance")
            kwargs.update({'user': self.object})
        return kwargs

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.success_url:
            # Send a signal that the profile has changed
            return self.success_url
        else:
            return reverse('userena_password_change_complete', kwargs={'username': self._user.username})

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        form_valid = super(PasswordChangeView, self).form_valid(form)
        userena_signals.password_complete.send(sender=None, user=self.object)
        return form_valid
