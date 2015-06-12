from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import logout as Signout
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from django.utils.translation import ugettext as _

from userena.forms import (ChangeEmailForm)
from userena.models import UserenaSignup
from userena.decorators import secure_required
from userena.utils import (get_profile_model, get_user_model,
                           get_user_profile)
from userena import signals as userena_signals
from userena import settings as userena_settings

from guardian.decorators import permission_required_or_403

import warnings

class ExtraContextTemplateView(TemplateView):
    """ Add extra context to a simple template view """
    extra_context = None

    def get_context_data(self, *args, **kwargs):
        context = super(ExtraContextTemplateView, self).get_context_data(*args, **kwargs)
        if self.extra_context:
            context.update(self.extra_context)
        return context

    # this view is used in POST requests, e.g. signup when the form is not valid
    post = TemplateView.get


@secure_required
def activate(request, activation_key,
             template_name='userena/activate_fail.html',
             retry_template_name='userena/activate_retry.html',
             success_url=None, extra_context=None):
    """
    Activate a user with an activation key.

    The key is a SHA1 string. When the SHA1 is found with an
    :class:`UserenaSignup`, the :class:`User` of that account will be
    activated.  After a successful activation the view will redirect to
    ``success_url``.  If the SHA1 is not found, the user will be shown the
    ``template_name`` template displaying a fail message.
    If the SHA1 is found but expired, ``retry_template_name`` is used instead,
    so the user can proceed to :func:`activate_retry` to get a new activation key.

    :param activation_key:
        String of a SHA1 string of 40 characters long. A SHA1 is always 160bit
        long, with 4 bits per character this makes it --160/4-- 40 characters
        long.

    :param template_name:
        String containing the template name that is used when the
        ``activation_key`` is invalid and the activation fails. Defaults to
        ``userena/activate_fail.html``.

    :param retry_template_name:
        String containing the template name that is used when the
        ``activation_key`` is expired. Defaults to
        ``userena/activate_retry.html``.

    :param success_url:
        String containing the URL where the user should be redirected to after
        a successful activation. Will replace ``%(username)s`` with string
        formatting if supplied. If ``success_url`` is left empty, will direct
        to ``userena_profile_detail`` view.

    :param extra_context:
        Dictionary containing variables which could be added to the template
        context. Default to an empty dictionary.

    """
    try:
        if (not UserenaSignup.objects.check_expired_activation(activation_key)
            or not userena_settings.USERENA_ACTIVATION_RETRY):
            user = UserenaSignup.objects.activate_user(activation_key)
            if user:
                # Sign the user in.
                auth_user = authenticate(identification=user.email,
                                         check_password=False)
                login(request, auth_user)

                if userena_settings.USERENA_USE_MESSAGES:
                    messages.success(request, _('Your account has been activated and you have been signed in.'),
                                     fail_silently=True)

                if success_url: redirect_to = success_url % {'username': user.username }
                else: redirect_to = reverse('userena_profile_detail',
                                            kwargs={'username': user.username})
                return redirect(redirect_to)
            else:
                if not extra_context: extra_context = dict()
                return ExtraContextTemplateView.as_view(template_name=template_name,
                                                        extra_context=extra_context)(
                                        request)
        else:
            if not extra_context: extra_context = dict()
            extra_context['activation_key'] = activation_key
            return ExtraContextTemplateView.as_view(template_name=retry_template_name,
                                                extra_context=extra_context)(request)
    except UserenaSignup.DoesNotExist:
        if not extra_context: extra_context = dict()
        return ExtraContextTemplateView.as_view(template_name=template_name,
                                                extra_context=extra_context)(request)

@secure_required
def activate_retry(request, activation_key,
                   template_name='userena/activate_retry_success.html',
                   extra_context=None):
    """
    Reissue a new ``activation_key`` for the user with the expired
    ``activation_key``.

    If ``activation_key`` does not exists, or ``USERENA_ACTIVATION_RETRY`` is
    set to False and for any other error condition user is redirected to
    :func:`activate` for error message display.

    :param activation_key:
        String of a SHA1 string of 40 characters long. A SHA1 is always 160bit
        long, with 4 bits per character this makes it --160/4-- 40 characters
        long.

    :param template_name:
        String containing the template name that is used when new
        ``activation_key`` has been created. Defaults to
        ``userena/activate_retry_success.html``.

    :param extra_context:
        Dictionary containing variables which could be added to the template
        context. Default to an empty dictionary.

    """
    if not userena_settings.USERENA_ACTIVATION_RETRY:
        return redirect(reverse('userena_activate', args=(activation_key,)))
    try:
        if UserenaSignup.objects.check_expired_activation(activation_key):
            new_key = UserenaSignup.objects.reissue_activation(activation_key)
            if new_key:
                if not extra_context: extra_context = dict()
                return ExtraContextTemplateView.as_view(template_name=template_name,
                                                    extra_context=extra_context)(request)
            else:
                return redirect(reverse('userena_activate',args=(activation_key,)))
        else:
            return redirect(reverse('userena_activate',args=(activation_key,)))
    except UserenaSignup.DoesNotExist:
        return redirect(reverse('userena_activate',args=(activation_key,)))

@secure_required
def email_confirm(request, confirmation_key,
                  template_name='userena/email_confirm_fail.html',
                  success_url=None, extra_context=None):
    """
    Confirms an email address with a confirmation key.

    Confirms a new email address by running :func:`User.objects.confirm_email`
    method. If the method returns an :class:`User` the user will have his new
    e-mail address set and redirected to ``success_url``. If no ``User`` is
    returned the user will be represented with a fail message from
    ``template_name``.

    :param confirmation_key:
        String with a SHA1 representing the confirmation key used to verify a
        new email address.

    :param template_name:
        String containing the template name which should be rendered when
        confirmation fails. When confirmation is successful, no template is
        needed because the user will be redirected to ``success_url``.

    :param success_url:
        String containing the URL which is redirected to after a successful
        confirmation.  Supplied argument must be able to be rendered by
        ``reverse`` function.

    :param extra_context:
        Dictionary of variables that are passed on to the template supplied by
        ``template_name``.

    """
    user = UserenaSignup.objects.confirm_email(confirmation_key)
    if user:
        if userena_settings.USERENA_USE_MESSAGES:
            messages.success(request, _('Your email address has been changed.'),
                             fail_silently=True)

        if success_url: redirect_to = success_url
        else: redirect_to = reverse('userena_email_confirm_complete',
                                    kwargs={'username': user.username})
        return redirect(redirect_to)
    else:
        if not extra_context: extra_context = dict()
        return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)

def direct_to_user_template(request, username, template_name,
                            extra_context=None):
    """
    Simple wrapper for Django's :func:`direct_to_template` view.

    This view is used when you want to show a template to a specific user. A
    wrapper for :func:`direct_to_template` where the template also has access to
    the user that is found with ``username``. For ex. used after signup,
    activation and confirmation of a new e-mail.

    :param username:
        String defining the username of the user that made the action.

    :param template_name:
        String defining the name of the template to use. Defaults to
        ``userena/signup_complete.html``.

    **Keyword arguments**

    ``extra_context``
        A dictionary containing extra variables that should be passed to the
        rendered template. The ``account`` key is always the ``User``
        that completed the action.

    **Extra context**

    ``viewed_user``
        The currently :class:`User` that is viewed.

    """
    user = get_object_or_404(get_user_model(), username__iexact=username)

    if not extra_context: extra_context = dict()
    extra_context['viewed_user'] = user
    extra_context['profile'] = get_user_profile(user=user)
    return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)

def disabled_account(request, username, template_name, extra_context=None):
    """
    Checks if the account is disabled, if so, returns the disabled account template.

    :param username:
        String defining the username of the user that made the action.

    :param template_name:
        String defining the name of the template to use. Defaults to
        ``userena/signup_complete.html``.

    **Keyword arguments**

    ``extra_context``
        A dictionary containing extra variables that should be passed to the
        rendered template. The ``account`` key is always the ``User``
        that completed the action.

    **Extra context**

    ``viewed_user``
        The currently :class:`User` that is viewed.

    ``profile``
        Profile of the viewed user.

    """
    user = get_object_or_404(get_user_model(), username__iexact=username)

    if user.is_active:
        raise Http404

    if not extra_context: extra_context = dict()
    extra_context['viewed_user'] = user
    extra_context['profile'] = get_user_profile(user=user)
    return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)

@secure_required
def signout(request, next_page=userena_settings.USERENA_REDIRECT_ON_SIGNOUT,
            template_name='userena/signout.html', *args, **kwargs):
    """
    Signs out the user and adds a success message ``You have been signed
    out.`` If next_page is defined you will be redirected to the URI. If
    not the template in template_name is used.

    :param next_page:
        A string which specifies the URI to redirect to.

    :param template_name:
        String defining the name of the template to use. Defaults to
        ``userena/signout.html``.

    """
    if request.user.is_authenticated() and userena_settings.USERENA_USE_MESSAGES: # pragma: no cover
        messages.success(request, _('You have been signed out.'), fail_silently=True)
    userena_signals.account_signout.send(sender=None, user=request.user)
    return Signout(request, next_page, template_name, *args, **kwargs)

@secure_required
@permission_required_or_403('change_user', (get_user_model(), 'username', 'username'))
def email_change(request, username, email_form=ChangeEmailForm,
                 template_name='userena/email_form.html', success_url=None,
                 extra_context=None):
    """
    Change email address

    :param username:
        String of the username which specifies the current account.

    :param email_form:
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
    user = get_object_or_404(get_user_model(), username__iexact=username)
    prev_email = user.email
    form = email_form(user)

    if request.method == 'POST':
        form = email_form(user, request.POST, request.FILES)

        if form.is_valid():
            form.save()

            if success_url:
                # Send a signal that the email has changed
                userena_signals.email_change.send(sender=None,
                                                  user=user,
                                                  prev_email=prev_email,
                                                  new_email=user.email)
                redirect_to = success_url
            else: redirect_to = reverse('userena_email_change_complete',
                                        kwargs={'username': user.username})
            return redirect(redirect_to)

    if not extra_context: extra_context = dict()
    extra_context['form'] = form
    extra_context['profile'] = get_user_profile(user=user)
    return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)

@secure_required
@permission_required_or_403('change_user', (get_user_model(), 'username', 'username'))
def password_change(request, username, template_name='userena/password_form.html',
                    pass_form=PasswordChangeForm, success_url=None, extra_context=None):
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

    :param pass_form:
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
    user = get_object_or_404(get_user_model(),
                             username__iexact=username)

    form = pass_form(user=user)

    if request.method == "POST":
        form = pass_form(user=user, data=request.POST)
        if form.is_valid():
            form.save()

            # Send a signal that the password has changed
            userena_signals.password_complete.send(sender=None,
                                                   user=user)

            if success_url: redirect_to = success_url
            else: redirect_to = reverse('userena_password_change_complete',
                                        kwargs={'username': user.username})
            return redirect(redirect_to)

    if not extra_context: extra_context = dict()
    extra_context['form'] = form
    extra_context['profile'] = get_user_profile(user=user)
    return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)


def profile_list(request, page=1, template_name='userena/profile_list.html',
                 paginate_by=50, extra_context=None, **kwargs): # pragma: no cover
    """
    Returns a list of all profiles that are public.

    It's possible to disable this by changing ``USERENA_DISABLE_PROFILE_LIST``
    to ``True`` in your settings.

    :param page:
        Integer of the active page used for pagination. Defaults to the first
        page.

    :param template_name:
        String defining the name of the template that is used to render the
        list of all users. Defaults to ``userena/list.html``.

    :param paginate_by:
        Integer defining the amount of displayed profiles per page. Defaults to
        50 profiles per page.

    :param extra_context:
        Dictionary of variables that are passed on to the ``template_name``
        template.

    **Context**

    ``profile_list``
        A list of profiles.

    ``is_paginated``
        A boolean representing whether the results are paginated.

    If the result is paginated. It will also contain the following variables.

    ``paginator``
        An instance of ``django.core.paginator.Paginator``.

    ``page_obj``
        An instance of ``django.core.paginator.Page``.

    """
    warnings.warn("views.profile_list is deprecated. Use ProfileListView instead", DeprecationWarning, stacklevel=2)

    try:
        page = int(request.GET.get('page', None))
    except (TypeError, ValueError):
        page = page

    if userena_settings.USERENA_DISABLE_PROFILE_LIST \
       and not request.user.is_staff:
        raise Http404

    profile_model = get_profile_model()
    queryset = profile_model.objects.get_visible_profiles(request.user)

    if not extra_context: extra_context = dict()
    from .profile import ProfileListView
    return ProfileListView.as_view(queryset=queryset,
                                   paginate_by=paginate_by,
                                   page=page,
                                   template_name=template_name,
                                   extra_context=extra_context,
                                   **kwargs)(request)
