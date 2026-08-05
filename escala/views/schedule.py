from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from escala.models import PushSubscription, Schedule
from escala.permissions import IsScheduleAccessible
from escala.serializers import CreateScheduleSerializer, RetrieveScheduleSerializer

from ..fcm import (
    send_schedule_deleted_notification,
    send_schedule_notification,
    send_schedule_updated_notification,
)


def _get_active_subscription_tokens(user_ids):
    return list(
        PushSubscription.objects.filter(
            user_id__in=user_ids,
            is_active=True,
            permission=PushSubscription.PERMISSION_GRANTED,
        )
        .values_list("token", flat=True)
        .distinct()
    )


def _deactivate_invalid_tokens(tokens):
    if tokens:
        PushSubscription.objects.filter(token__in=tokens).update(is_active=False)


class SchedulePagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class ScheduleViewSet(ModelViewSet):
    queryset = Schedule.objects.all()
    pagination_class = SchedulePagination
    permission_classes = [IsScheduleAccessible]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        scope = self.request.query_params.get("scope")
        filter_value = self.request.query_params.get("filter", "all").lower()

        scope = (scope or "all").lower()
        if scope not in {"all", "mine"}:
            raise ValidationError({"scope": "Os valores permitidos são 'all' e 'mine'."})

        queryset = queryset.filter(
            Q(team__members=user) | Q(team__admins=user)
        ).distinct()

        if scope == "mine":
            queryset = queryset.filter(participations__user=user).distinct()

        timezone.activate("America/Sao_Paulo")
        local_date = timezone.localtime(timezone.now()).date()

        match filter_value:
            case "next":
                queryset = queryset.filter(date__gte=local_date)
                return queryset.order_by("date", "hour")
            case "past":
                queryset = queryset.filter(date__lt=local_date)
                return queryset.order_by("-date", "-hour")
            case "week":
                end_date = local_date + timedelta(days=7)
                queryset = queryset.filter(date__gte=local_date, date__lte=end_date)
                return queryset.order_by("date", "hour")
            case _:
                return queryset.order_by("date", "hour")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return CreateScheduleSerializer
        if self.action in ["list", "retrieve"]:
            return RetrieveScheduleSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save()

        participant_user_ids = schedule.participations.values_list("user_id", flat=True)
        tokens = _get_active_subscription_tokens(participant_user_ids)

        invalid_tokens = send_schedule_notification(
            fcm_tokens=tokens,
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            schedule_date=schedule.date,
            schedule_hour=schedule.hour,
        )

        _deactivate_invalid_tokens(invalid_tokens)

        output_serializer = RetrieveScheduleSerializer(
            schedule, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        schedule = self.get_object()
        previous_user_ids = set(
            schedule.participations.values_list("user_id", flat=True)
        )
        serializer = self.get_serializer(
            schedule,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        current_user_ids = set(
            schedule.participations.values_list("user_id", flat=True)
        )
        removed_user_ids = previous_user_ids - current_user_ids
        invalid_tokens = []

        current_tokens = _get_active_subscription_tokens(current_user_ids)
        if current_tokens:
            invalid_tokens.extend(
                send_schedule_updated_notification(
                    fcm_tokens=current_tokens,
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    schedule_date=schedule.date,
                    schedule_hour=schedule.hour,
                    participant_removed=False,
                )
            )

        removed_tokens = _get_active_subscription_tokens(removed_user_ids)
        if removed_tokens:
            invalid_tokens.extend(
                send_schedule_updated_notification(
                    fcm_tokens=removed_tokens,
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    schedule_date=schedule.date,
                    schedule_hour=schedule.hour,
                    participant_removed=True,
                )
            )

        _deactivate_invalid_tokens(invalid_tokens)

        if getattr(schedule, "_prefetched_objects_cache", None):
            schedule._prefetched_objects_cache = {}

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        schedule = self.get_object()
        participant_user_ids = list(
            schedule.participations.values_list("user_id", flat=True)
        )
        tokens = _get_active_subscription_tokens(participant_user_ids)
        notification_data = {
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "schedule_date": schedule.date,
            "schedule_hour": schedule.hour,
        }

        self.perform_destroy(schedule)

        if tokens:
            invalid_tokens = send_schedule_deleted_notification(
                fcm_tokens=tokens,
                **notification_data,
            )
            _deactivate_invalid_tokens(invalid_tokens)

        return Response(status=status.HTTP_204_NO_CONTENT)
