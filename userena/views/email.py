from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView

from guardian.decorators import permission_required_or_403

from userena.decorators import secure_required
from userena.forms import ChangeEmailForm
from userena.utils import get_user_model
from userena import signals as userena_signals

from .mixins import ExtraContextMixin


class EmailChangeView(ExtraContextMixin, UpdateView):

    """
    Change email address

    :param username:
        String of the username which specifies the current account.

    :param class_form:
        Form that will be used to change the email address. Defaults to
        :class:`ChangeEmailForm` supplied by userena.

    :param template_name:
        String containing the template to be used to display the email form.
        Defaults to ``userena/email_form.html``.

    :param success_url:
        Named URL where the user will get redirected to when successfully
        changing their email address.  When not supplied will redirect to
        ``userena_email_complete`` URL.

    :param extra_context:
        Dictionary containing extra variables that can be used to render the
        template. The ``form`` key is always the form supplied by the keyword
        argument ``form`` and the ``user`` key by the user whose email address
        is being changed.

    **Context**

    ``form``
        Form that is used to change the email address supplied by ``form``.

    ``account``
        Instance of the ``Account`` whose email address is about to be changed.

    **Todo**

    Need to have per-object permissions, which enables users with the correct
    permissions to alter the email address of others.

    """

    model = get_user_model()
    form_class = ChangeEmailForm
    slug_field = "username__iexact"
    slug_url_kwarg = 'username'
    success_url = None
    template_name = 'userena/email_form.html'

    @method_decorator(secure_required)
    @method_decorator(permission_required_or_403('change_user',
                                                 (get_user_model(),
                                                  'username',
                                                  'username')))
    def dispatch(self, request, *args, **kwargs):
        return super(EmailChangeView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super(EmailChangeView, self).get_object()
        self.prev_email = obj.email
        return obj

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super(EmailChangeView, self).get_form_kwargs()
        if hasattr(self, 'object'):
            self._user = kwargs.pop("instance")
            kwargs.update({'user': self.object})
        return kwargs

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.success_url:
            userena_signals.email_change.send(sender=None,
                                              user=self._user,
                                              prev_email=self.prev_email,
                                              new_email=self._user.email)
            url = self.success_url
        else:
            url = reverse('userena_email_change_complete',
                          kwargs={'username': self._user.username})
        return url
