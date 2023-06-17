"""Djanago module for data copy and track the activities."""

__version__ = "0.1.0"


from django.db import models


class RowStatus(models.TextChoices):
    CREATED = "C", "Created"
    UPDATED = "U", "Updated"
    IGNORED = "I", "Ignored"
    DELETED = "D", "Deleted"
    UNKNOWN = "X", "Unknown"


__all__ = ["RowStatus"]
