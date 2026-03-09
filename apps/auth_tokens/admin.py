from django.contrib import admin
from django.utils import timezone

from .models import InviteToken


class InviteStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("expired", "Expired"), ("used", "Used"))

    def queryset(self, request, queryset):
        value = self.value()
        now = timezone.now()
        if value == "active":
            return queryset.filter(used_at__isnull=True, expires_at__gt=now)
        if value == "expired":
            return queryset.filter(used_at__isnull=True, expires_at__lte=now)
        if value == "used":
            return queryset.filter(used_at__isnull=False)
        return queryset


@admin.register(InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "assigned_to",
        "created_by",
        "created_at",
        "expires_at",
        "used_at",
    )
    search_fields = ("token", "assigned_to__username", "created_by__username")
    list_filter = (InviteStatusFilter, "created_at", "expires_at", "used_at")
    readonly_fields = ("token", "created_at", "used_at")
