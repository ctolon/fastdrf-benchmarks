from bench.api.drf import serializers, views
from bench.api.routes import routes

urlpatterns = routes(views, serializers)
