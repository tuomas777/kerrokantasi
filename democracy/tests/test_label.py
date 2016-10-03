# -*- coding: utf-8 -*-
import pytest

from democracy.models import Label
from democracy.tests.utils import get_data_from_response


def test_label_str():
    assert str(Label(label="label")) == "label"


@pytest.mark.django_db
def test_get_label_list_check_fields(api_client, random_label):
    data = get_data_from_response(api_client.get('/v1/label/'))
    assert len(data['results']) == 1

    label_data = data['results'][0]
    assert set(label_data.keys()) == {'id', 'label', 'created_at', 'modified_at'}
    assert label_data['id'] == random_label.id
    assert label_data['label'] == random_label.label
