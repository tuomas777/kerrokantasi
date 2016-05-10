import pytest
from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from democracy.models import Hearing


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
def test_hearing_delete_action(admin_client, default_hearing):
    change_url = reverse('admin:democracy_hearing_changelist')
    data = {'action': 'delete_selected', '_selected_action': [default_hearing.pk]}
    response = admin_client.post(change_url, data, follow=True)

    assert response.status_code == 200
    assert 'Successfully deleted 1 hearing.' in response.rendered_content

    default_hearing = Hearing.objects.everything().get(pk=default_hearing.pk)
    assert default_hearing.deleted is True