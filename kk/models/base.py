from django.core.exceptions import ValidationError
from functools import lru_cache

from django.conf import settings
from django.db import models
from django.db.models import ManyToOneRel
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from enumfields.fields import EnumIntegerField

from kk.enums import Commenting


def generate_id():
    return get_random_string(32)


class BaseModelManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(deleted=True)

    def public(self, *args, **kwargs):
        return self.get_queryset().exclude(published=False).filter(*args, **kwargs)

    def with_unpublished(self, *args, **kwargs):
        return self.get_queryset().filter(*args, **kwargs)

    def deleted(self, *args, **kwargs):
        return super().get_queryset().filter(deleted=True).filter(*args, **kwargs)

    def everything(self, *args, **kwargs):
        return super().get_queryset().filter(*args, **kwargs)


class BaseModel(models.Model):
    created_at = models.DateTimeField(verbose_name=_('Time of creation'), default=timezone.now, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('Created by'),
        null=True, blank=True, related_name="%(class)s_created",
        editable=False
    )
    modified_at = models.DateTimeField(verbose_name=_('Time of modification'), default=timezone.now, editable=False)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('Modified by'),
        null=True, blank=True, related_name="%(class)s_modified",
        editable=False
    )
    published = models.BooleanField(verbose_name=_('Publish flag'), default=True, db_index=True)
    deleted = models.BooleanField(
        verbose_name=_('Deleted flag'), default=False, db_index=True,
        editable=False
    )
    objects = BaseModelManager()

    def save(self, *args, **kwargs):
        pk_type = self._meta.pk.get_internal_type()
        if pk_type == 'CharField':
            if not self.pk:
                self.pk = generate_id()
        elif pk_type == 'AutoField':
            pass
        else:  # pragma: no cover
            raise Exception('Unsupported primary key field: %s' % pk_type)
        if not kwargs.pop("no_modified_at_update", False):
            # Useful for importing, etc.
            self.modified_at = timezone.now()
        super().save(*args, **kwargs)

    def soft_delete(self, using=None):
        self.deleted = True
        self.save(update_fields=("deleted",), using=using, force_update=True)

    def delete(self, using=None):
        raise NotImplementedError("This model does not support hard deletion")

    @classmethod
    @lru_cache()
    def find_subclass(cls, parent_model):
        """
        Find the subclass that's used with the given `parent_model`.

        This is only useful for models that are related to another model, such
        as Comments or Images.

        :param parent_model: A model (class or instance)
        :return: The model subclass, or None
        :rtype: class|None
        """
        for field in parent_model._meta.get_fields():  # pragma: no branch
            if isinstance(field, ManyToOneRel) and issubclass(field.related_model, cls):  # pragma: no branch
                return field.related_model

    class Meta:
        abstract = True


class StringIdBaseModel(BaseModel):
    id = models.CharField(
        primary_key=True,
        max_length=32,
        blank=True,
        help_text=_('You may leave this empty to automatically generate an ID')
    )

    class Meta:
        abstract = True


class Commentable(models.Model):
    """
    Mixin for models which can be commented.
    """
    n_comments = models.IntegerField(verbose_name=_('Number of comments'), blank=True, default=0, editable=False)
    commenting = EnumIntegerField(Commenting, default=Commenting.NONE)

    def recache_n_comments(self):
        new_n_comments = self.comments.count()
        if new_n_comments != self.n_comments:
            self.n_comments = new_n_comments
            self.save(update_fields=("n_comments",))

    def may_comment(self, request):
        is_authenticated = request.user.is_authenticated()
        if self.commenting == Commenting.NONE:
            raise ValidationError(_("%s does not allow commenting") % self, code="commenting_none")
        elif self.commenting == Commenting.REGISTERED:
            if not is_authenticated:
                raise ValidationError(_("%s does not allow anonymous commenting") % self, code="commenting_registered")
            return True
        elif self.commenting == Commenting.OPEN:
            return True
        else:  # pragma: no cover
            raise NotImplementedError("Not implemented")

    class Meta:
        abstract = True
