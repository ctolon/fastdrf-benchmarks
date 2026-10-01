from bench.api.fast import serializers, views
from bench.api.routes import routes

urlpatterns = routes(views, serializers)
