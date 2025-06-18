from django.urls import re_path
from main.consumers import QuizConsumer

websocket_urlpatterns = [
    re_path(r'ws/quiz/(?P<quiz_id>\d+)/$', QuizConsumer.as_asgi()),
]
