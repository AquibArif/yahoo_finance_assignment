from django.conf.urls import url
from yahoo import views

urlpatterns = [
    url(r'^dashboard/$', views.display_dashboard, name="display_dashboard"),
    url(r'^compute_data/$', views.compute_data, name="compute_data"),
]
