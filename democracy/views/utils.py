# -*- coding: utf-8 -*-
from functools import lru_cache

from django.core.exceptions import ImproperlyConfigured
from django.db.models.query import QuerySet
from django.utils.timezone import now
from rest_framework import serializers
from rest_framework.relations import ManyRelatedField, MANY_RELATION_KWARGS


class AbstractFieldSerializer(serializers.RelatedField):
    parent_serializer_class = serializers.ModelSerializer
    many_field_class = ManyRelatedField

    def to_representation(self, image):
        return self.parent_serializer_class(image, context=self.context).data

    @classmethod
    def many_init(cls, *args, **kwargs):
        list_kwargs = {'child_relation': cls(*args, **kwargs)}
        for key in kwargs.keys():
            if key in MANY_RELATION_KWARGS:
                list_kwargs[key] = kwargs[key]
        return cls.many_field_class(**list_kwargs)


class AbstractSerializerMixin(object):

    @classmethod
    @lru_cache()
    def get_field_serializer_class(cls, many_field_class=ManyRelatedField):
        return type('%sFieldSerializer' % cls.Meta.model, (AbstractFieldSerializer,), {
            "parent_serializer_class": cls,
            "many_field_class": many_field_class,
        })

    @classmethod
    def get_field_serializer(cls, **kwargs):
        many_field_class = kwargs.pop("many_field_class", ManyRelatedField)
        return cls.get_field_serializer_class(many_field_class=many_field_class)(**kwargs)


class IOErrorIgnoringManyRelatedField(ManyRelatedField):
    """
    A ManyRelatedField that ignores IOErrors occurring during iterating the children.

    This is mainly useful for images that are referenced in the database but do not exist
    on the server (where constructing them requires accessing them to populate the width
    and height fields).
    """
    def to_representation(self, iterable):
        out = []
        if isinstance(iterable, QuerySet):
            iterable = iterable.iterator()
        while True:
            try:
                value = next(iterable)
                out.append(self.child_relation.to_representation(value))
            except StopIteration:
                break
            except IOError:
                continue
        return out


class PublicFilteredImageField(serializers.Field):

    def __init__(self, *args, **kwargs):
        self.serializer_class = kwargs.pop('serializer_class', None)
        if not self.serializer_class:
            raise ImproperlyConfigured('Keyword argument serializer_class required')
        super().__init__(*args, **kwargs)

    def to_representation(self, images):
        request = self.context.get('request')

        if request and request.user and request.user.is_authenticated() and request.user.is_superuser:
            images = images.with_unpublished()
        else:
            images = images.public()

        serializer = self.serializer_class.get_field_serializer(
            many=True, read_only=True, many_field_class=IOErrorIgnoringManyRelatedField
        )
        serializer.bind(self.source, self)  # this is needed to get context in the serializer

        return serializer.to_representation(images)


def filter_by_hearing_visible(queryset, request, hearing_lookup='hearing'):
    filters = {
        '%s__deleted' % hearing_lookup: False,
        '%s__open_at__lte' % hearing_lookup: now()
    }

    if not request.user.is_superuser:
        filters['%s__published' % hearing_lookup] = True

    return queryset.filter(**filters)
