import django_filters
from django.db.models import Prefetch
from django.utils.timezone import now
from rest_framework import filters, permissions, response, serializers, status, viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.fields import JSONField
from rest_framework.exceptions import NotFound
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from democracy.enums import InitialSectionType
from democracy.models import ContactPerson, Hearing, Section, SectionImage
from democracy.views.base import AdminsSeeUnpublishedMixin
from democracy.views.label import LabelSerializer
from democracy.views.section import SectionFieldSerializer, SectionImageSerializer

from .hearing_report import HearingReport


class ContactPersonSerializer(serializers.ModelSerializer):
    organization = serializers.SlugRelatedField('name', read_only=True)

    class Meta:
        model = ContactPerson
        fields = ('name', 'title', 'phone', 'email', 'organization')


class HearingFilter(django_filters.FilterSet):
    open_at_lte = django_filters.IsoDateTimeFilter(name='open_at', lookup_type='lte')
    open_at_gt = django_filters.IsoDateTimeFilter(name='open_at', lookup_type='gt')

    class Meta:
        model = Hearing
        fields = ['published', 'open_at_lte', 'open_at_gt']


class HearingSerializer(serializers.ModelSerializer):
    labels = LabelSerializer(many=True, read_only=True)
    sections = serializers.SerializerMethodField()
    geojson = JSONField()
    organization = serializers.SlugRelatedField(
        read_only=True,
        slug_field='name'
    )
    main_image = serializers.SerializerMethodField()
    abstract = serializers.SerializerMethodField()
    contact_persons = ContactPersonSerializer(many=True, read_only=True)

    def get_abstract(self, hearing):
        prefetched_mains = getattr(hearing, 'main_section_list', [])
        main_section = prefetched_mains[0] if prefetched_mains else hearing.get_main_section()
        return main_section.abstract if main_section else ''

    def get_sections(self, hearing):
        queryset = hearing.sections.all()
        if not hearing.closed:
            queryset = queryset.exclude(type__identifier=InitialSectionType.CLOSURE_INFO)

        serializer = SectionFieldSerializer(many=True, read_only=True)
        serializer.bind('sections', self)  # this is needed to get context in the serializer
        return serializer.to_representation(queryset)

    def get_main_image(self, hearing):
        main_image = SectionImage.objects.filter(
            section__hearing=hearing,
            section__type__identifier='main'
        ).first()

        if not main_image:
            return None

        if main_image.published or self.context['request'].user.is_superuser:
            return SectionImageSerializer(context=self.context, instance=main_image).data
        else:
            return None

    class Meta:
        model = Hearing
        fields = [
            'abstract', 'title', 'id', 'borough', 'n_comments',
            'published', 'labels', 'open_at', 'close_at', 'created_at',
            'servicemap_url', 'sections',
            'closed', 'geojson', 'organization', 'slug', 'main_image', 'contact_persons'
        ]


class HearingListSerializer(HearingSerializer):

    def get_fields(self):
        fields = super(HearingListSerializer, self).get_fields()
        # Elide section and geo data when listing hearings; one can get to them via detail routes
        fields.pop("sections")
        fields.pop("geojson")
        return fields


class HearingMapSerializer(serializers.ModelSerializer):
    geojson = JSONField()

    class Meta:
        model = Hearing
        fields = [
            'id', 'title', 'borough', 'open_at', 'close_at', 'closed', 'geojson', 'slug'
        ]


class HearingPagination(LimitOffsetPagination):
    default_limit = 50


class HearingViewSet(AdminsSeeUnpublishedMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for hearings.
    """
    model = Hearing
    serializer_class = HearingSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    pagination_class = HearingPagination

    # ordering_fields = ('created_at',)
    # ordering = ('-created_at',)
    filter_class = HearingFilter

    def get_serializer(self, *args, **kwargs):
        if kwargs.get("many"):  # List serialization?
            serializer_class = HearingListSerializer
        else:
            serializer_class = HearingSerializer
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def common_queryset_filtering(self, queryset):
        """
        Apply common time filters etc to the queryset.

        Used by both get_queryset() and get_object().
        """
        next_closing = self.request.query_params.get('next_closing', None)
        if next_closing is not None:
            return queryset.filter(close_at__gt=next_closing).order_by('close_at')[:1]
        return queryset.order_by('-created_at')

    def get_queryset(self):
        queryset = super(HearingViewSet, self).get_queryset().prefetch_related(
            Prefetch(
                'sections',
                queryset=Section.objects.filter(type__identifier='main'),
                to_attr='main_section_list'
            )
        )

        # unless the user is a superuser, only show open hearings in the hearing list
        if not self.request.user.is_superuser:
            queryset = queryset.filter(open_at__lte=now())

        return self.common_queryset_filtering(queryset)

    def get_object(self):
        id_or_slug = self.kwargs[self.lookup_url_kwarg or self.lookup_field]

        queryset = self.common_queryset_filtering(Hearing.objects.with_unpublished())
        queryset = queryset.prefetch_related(
            Prefetch(
                'sections',
                queryset=Section.objects.filter(type__identifier='main'),
                to_attr='main_section_list'
            )
        )

        try:
            obj = queryset.get_by_id_or_slug(id_or_slug)
        except Hearing.DoesNotExist:
            raise NotFound()

        is_superuser = self.request.user.is_superuser
        preview_code = None
        if not obj.published and not is_superuser:
            preview_code = self.request.query_params.get('preview')
            if not preview_code or preview_code != obj.preview_code:
                raise NotFound()

        # require preview_code or superuser status to show a not yet opened hearing
        if not (preview_code or is_superuser or obj.open_at <= now()):
            raise NotFound()

        self.check_object_permissions(self.request, obj)
        return obj

    @detail_route(methods=['post'])
    def follow(self, request, pk=None):
        hearing = self.get_object()

        # check if user already follow a hearing
        if Hearing.objects.filter(id=hearing.id, followers=request.user).exists():
            return response.Response({'status': 'Already follow'}, status=status.HTTP_304_NOT_MODIFIED)

        # add follower
        hearing.followers.add(request.user)

        # return success
        return response.Response({'status': 'You follow a hearing now'}, status=status.HTTP_201_CREATED)

    @detail_route(methods=['post'])
    def unfollow(self, request, pk=None):
        hearing = self.get_object()

        if Hearing.objects.filter(id=hearing.id, followers=request.user).exists():
            hearing.followers.remove(request.user)
            return response.Response({'status': 'You stopped following a hearing'}, status=status.HTTP_204_NO_CONTENT)

        return response.Response({'status': 'You are not following this hearing'}, status=status.HTTP_304_NOT_MODIFIED)

    @detail_route(methods=['get'])
    def report(self, request, pk=None):
        report = HearingReport(HearingSerializer(self.get_object(), context=self.get_serializer_context()).data)
        return report.get_response()

    @list_route(methods=['get'])
    def map(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = HearingMapSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = HearingMapSerializer(queryset, many=True)
        return Response(serializer.data)
