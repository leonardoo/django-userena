from django.contrib.auth.forms import PasswordChangeForm
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView

from guardian.decorators import permission_required_or_403

from userena.decorators import secure_required
from userena.utils import (get_user_model)
from userena import signals as userena_signals


class PasswordChangeView(UpdateView):

    model = get_user_model()
    form_class = PasswordChangeForm
    slug_url_kwarg = 'username'
    slug_field = "username__iexact"
    success_url = None
    template_name='userena/password_form.html'

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
