from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """
    A conversation between exactly two users (a Client and a Freelancer,
    in practice). We don't hardcode "client"/"freelancer" fields here —
    just two generic participants — so the same model works no matter
    who started the conversation.
    """

    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_a"
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_b"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def other_user(self, current_user):
        """Given one participant, returns the other one — used constantly in templates/views."""
        return self.participant_b if self.participant_a == current_user else self.participant_a

    def last_message(self):
        return self.messages.last()

    def __str__(self):
        return f"Conversation between {self.participant_a.username} and {self.participant_b.username}"


class Message(models.Model):
    """A single chat message within a Conversation."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(blank=True)  # Made optional so users can send pure file uploads
    file = models.FileField(upload_to="chat_attachments/", blank=True, null=True)  # Added file attachments
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.username}: {self.text[:30]}"