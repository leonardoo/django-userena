from django.conf.urls import *

from userena import views

PROFILE = [
    # View profiles
    url(r'^(?P<username>(?!signout|signup|signin)[\@\.\w-]+)/$',
        views.profile_detail,
        name='userena_profile_detail'),
]

urlpatterns = patterns('',
    url(r'^accounts/', include(PROFILE)),
)
