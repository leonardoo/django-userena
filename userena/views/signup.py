from django.contrib.auth import logout, authenticate, login
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import FormView

from userena.decorators import secure_required
from userena.forms import SignupForm, SignupFormOnlyEmail
from userena import signals as userena_signals
from userena import settings as userena_settings

from .mixins import ExtraContextMixin


class SignupView(ExtraContextMixin, FormView):

    """
    Signup of an account.

    Signup requiring a username, email and password. After signup a user gets
    an email with an activation link used to activate their account. After
    successful signup redirects to ``success_url``.

    :param form_class:
        Form that will be used to sign a user. Defaults to userena's
        :class:`SignupForm`.

    :param template_name:
        String containing the template name that will be used to display the
        signup form. Defaults to ``userena/signup_form.html``.

    :param success_url:
        String containing the URI which should be redirected to after a
        successful signup. If not supplied will redirect to
        ``userena_signup_complete`` view.

    :param extra_context:
        Dictionary containing variables which are added to the template
        context. Defaults to a dictionary with a ``form`` key containing the
        ``signup_form``.

    **Context**

    ``form``
        Form supplied by ``form_class``.

    """

    template_name = 'userena/signup_form.html'
    form_class = SignupForm

    @method_decorator(secure_required)
    def dispatch(self, request, *args, **kwargs):

        # If signup is disabled, return 403
        if userena_settings.USERENA_DISABLE_SIGNUP:
            raise PermissionDenied
        return super(SignupView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        # Send the signup complete signal
        self.object = form.save()
        userena_signals.signup_complete.send(sender=None,
                                             user=self.object)

        # A new signed user should logout the old one.
        if self.request.user.is_authenticated():
            logout(self.request)

        if (userena_settings.USERENA_SIGNIN_AFTER_SIGNUP and
           not userena_settings.USERENA_ACTIVATION_REQUIRED):
            user = authenticate(identification=self.object.email, check_password=False)
            login(self.request, user)

        return super(SignupView, self).form_valid(form)

    def get_form_class(self):
        """
        Returns the form class to use in this view
        """
        # If no usernames are wanted and the default form is used, fallback to the
        # default form that doesn't display to enter the username.
        if userena_settings.USERENA_WITHOUT_USERNAMES and (self.form_class == SignupForm):
            self.form_class = SignupFormOnlyEmail
        return self.form_class

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.success_url:
            url = self.success_url
        else:
            url = reverse('userena_signup_complete', kwargs={'username': self.object.username})
        return url
