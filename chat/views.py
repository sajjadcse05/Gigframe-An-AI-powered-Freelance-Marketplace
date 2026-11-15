from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from .forms import MessageForm
from .models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    """List every conversation the logged-in user is part of, newest first."""
    conversations = Conversation.objects.filter(
        Q(participant_a=request.user) | Q(participant_b=request.user)
    )
    # Attach the "other participant" directly onto each conversation object
    # here in Python, since templates can't call other_user(request.user)
    # with an argument the way {{ conv.other_user }} alone can.
    for conv in conversations:
        conv.other = conv.other_user(request.user)
    return render(request, "chat/inbox.html", {"conversations": conversations})


@login_required
def start_conversation(request, user_id):
    """
    Called when someone clicks "Contact Freelancer" / "Message Client".
    get_or_create-style logic: if these two users already have a
    conversation, reuse it instead of creating a duplicate thread.
    """
    other_user = get_object_or_404(User, pk=user_id)

    if other_user == request.user:
        return redirect("chat_inbox")

    conversation = Conversation.objects.filter(
        Q(participant_a=request.user, participant_b=other_user) |
        Q(participant_a=other_user, participant_b=request.user)
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(participant_a=request.user, participant_b=other_user)

    return redirect("conversation_detail", pk=conversation.pk)


@login_required
def conversation_detail(request, pk):
    """
    Shows the full message thread. Also marks every message sent BY
    THE OTHER PERSON as read, since the current user is now viewing them.
    """
    conversation = get_object_or_404(
        Conversation.objects.filter(Q(participant_a=request.user) | Q(participant_b=request.user)),
        pk=pk,
    )
    conversation.messages.exclude(sender=request.user).update(is_read=True)

    messages = conversation.messages.all()
    other_user = conversation.other_user(request.user)

    return render(request, "chat/conversation_detail.html", {
        "conversation": conversation,
        "messages": messages,
        "other_user": other_user,
        "form": MessageForm(),
    })


@login_required
def send_message(request, pk):
    """
    Handles a new message being sent (text and/or file attachment).
    Returns JSON used by the JS script to update the UI without page reloads.
    """
    conversation = get_object_or_404(
        Conversation.objects.filter(Q(participant_a=request.user) | Q(participant_b=request.user)),
        pk=pk,
    )

    if request.method == "POST":
        # Pass request.FILES to bind uploaded attachments properly
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()

            return JsonResponse({
                "id": message.id,
                "text": message.text,
                "file_url": message.file.url if message.file else None,
                "sender": message.sender.username,
                "is_mine": True,
                "created_at": message.created_at.strftime("%H:%M"),
            })

    return JsonResponse({"error": "invalid request"}, status=400)


@login_required
def poll_messages(request, pk, after_id):
    """
    Called repeatedly by JavaScript every few seconds. Returns only
    messages newer than `after_id` — includes attached file URLs if available.
    """
    conversation = get_object_or_404(
        Conversation.objects.filter(Q(participant_a=request.user) | Q(participant_b=request.user)),
        pk=pk,
    )

    new_messages = conversation.messages.filter(id__gt=after_id).exclude(sender=request.user)
    new_messages.update(is_read=True)

    data = [{
        "id": m.id,
        "text": m.text,
        "file_url": m.file.url if m.file else None,
        "sender": m.sender.username,
        "is_mine": False,
        "created_at": m.created_at.strftime("%H:%M"),
    } for m in new_messages]

    return JsonResponse({"messages": data})


@login_required
def widget_init(request, user_id):
    """
    Called by the floating chat widget's JavaScript when it first opens.
    Returns JSON (conversation id + recent messages including files).
    """
    other_user = get_object_or_404(User, pk=user_id)

    if other_user == request.user:
        return JsonResponse({"error": "cannot message yourself"}, status=400)

    conversation = Conversation.objects.filter(
        Q(participant_a=request.user, participant_b=other_user) |
        Q(participant_a=other_user, participant_b=request.user)
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(participant_a=request.user, participant_b=other_user)

    conversation.messages.exclude(sender=request.user).update(is_read=True)
    messages = conversation.messages.all()

    return JsonResponse({
        "conversation_id": conversation.pk,
        "other_username": other_user.username,
        "messages": [{
            "id": m.id,
            "text": m.text,
            "file_url": m.file.url if m.file else None,
            "is_mine": m.sender == request.user,
            "created_at": m.created_at.strftime("%H:%M"),
        } for m in messages],
    })