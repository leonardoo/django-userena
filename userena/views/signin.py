from django.contrib import messages
from django.contrib.auth import authenticate, login, REDIRECT_FIELD_NAME
from django.core.urlresolvers import reverse
from django.views.generic import FormView
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from userena.decorators import secure_required
from userena.forms import (AuthenticationForm)
from userena.utils import (signin_redirect)
from userena import signals as userena_signals
from userena import settings as userena_settings


class SigninView(FormView):

    """
    Signin using email or username with password.

    Signs a user in by combining email/username with password. If the
    combination is correct and the user :func:`is_active` the
    :func:`redirect_signin_function` is called with the arguments
    ``REDIRECT_FIELD_NAME`` and an instance of the :class:`User` who is is
    trying the login. The returned value of the function will be the URL that
    is redirected to.

    A user can also select to be remembered for ``USERENA_REMEMBER_DAYS``.

    :param form_class:
        Form to use for signing the user in. Defaults to the
        :class:`AuthenticationForm` supplied by userena.

    :param template_name:
        String defining the name of the template to use. Defaults to
        ``userena/signin_form.html``.

    :param redirect_field_name:
        Form field name which contains the value for a redirect to the
        succeeding page. Defaults to ``next`` and is set in
        ``REDIRECT_FIELD_NAME`` setting.

    :param redirect_signin_function:
        Function which handles the redirect. This functions gets the value of
        ``REDIRECT_FIELD_NAME`` and the :class:`User` who has logged in. It
        must return a string which specifies the URI to redirect to.

    :param extra_context:
        A dictionary containing extra variables that should be passed to the
        rendered template. The ``form`` key is always the ``auth_form``.

    **Context**

    ``form``
        Form used for authentication supplied by ``auth_form``.

    """

    extra_context = None
    form_class = AuthenticationForm
    redirect_field_name = REDIRECT_FIELD_NAME
    redirect_signin_function = signin_redirect
    template_name = 'userena/signin_form.html'

    @method_decorator(secure_required)
    def dispatch(self, request, *args, **kwargs):
        return super(SigninView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        identification, password, remember_me = (form.cleaned_data['identification'],
                                                 form.cleaned_data['password'],
                                                 form.cleaned_data['remember_me'])
        user = authenticate(identification=identification, password=password)
        self.object = user
        if user.is_active:
            login(self.request, user)
            if remember_me:
                self.request.session.set_expiry(userena_settings.USERENA_REMEMBER_ME_DAYS[1] * 86400)
            else:
                self.request.session.set_expiry(0)

            if userena_settings.USERENA_USE_MESSAGES:
                messages.success(self.request, _('You have been signed in.'), fail_silently=True)

            #send a signal that a user has signed in
            userena_signals.account_signin.send(sender=None, user=user)


        return super(SigninView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super(SigninView, self).get_context_data(*args, **kwargs)
        if self.extra_context:
            context.update(self.extra_context)
            context.update({
                'next': self.REQUEST.get(self.redirect_field_name),
            })
        return context

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.object.is_active:
            return signin_redirect(redirect=self.REQUEST.get(self.redirect_field_name),
                                   user=self.object)
        else:
            return reverse('userena_disabled', kwargs={'username': self.object.username})

    @property
    def REQUEST(self):
        return getattr(self.request, self.request.method)

