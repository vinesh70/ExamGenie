import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.urls import reverse
from .models import Quiz

class QuizLinkConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.quiz_id = self.scope["url_route"]["kwargs"]["quiz_id"]
        self.room_group_name = f"quiz_{self.quiz_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        quiz_id = data.get("quiz_id")

        if quiz_id:
            quiz = Quiz.objects.get(id=quiz_id)
            quiz_link = reverse("take_quiz", kwargs={"quiz_code": quiz.quiz_code})

            # Send the generated quiz link to all connected clients
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "send_quiz_link",
                    "quiz_link": quiz_link,
                },
            )

    async def send_quiz_link(self, event):
        await self.send(text_data=json.dumps({"quiz_link": event["quiz_link"]}))
