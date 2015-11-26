import pytest
import reversion
from django.utils.encoding import force_text
from django.utils.timezone import now

from kk.enums import Commenting
from kk.models import Hearing, HearingComment, Section
from kk.tests.conftest import default_comment_content, green_comment_content, red_comment_content
from kk.tests.test_images import get_hearing_detail_url
from kk.tests.utils import assert_datetime_fuzzy_equal, get_data_from_response

comment_data = {
    'content': default_comment_content,
    'section': None
}


@pytest.mark.django_db
def test_55_add_comment_without_authentication(api_client, default_hearing):
    # post data to hearing ednpoint /v1/hearings/<hearingID>/comments/
    response = api_client.post(get_hearing_detail_url(default_hearing.id, 'comments'), data=comment_data)
    assert response.status_code == 201


@pytest.mark.django_db
def test_55_add_comment_to_hearing(john_doe, john_doe_api_client, default_hearing):
    # post data to hearing ednpoint /v1/hearings/<hearingID>/comments/
    response = john_doe_api_client.post(get_hearing_detail_url(default_hearing.id, 'comments'), data=comment_data)
    data = get_data_from_response(response, status_code=201)
    assert data['created_by']['username'] == john_doe.username
    assert data['content'] == default_comment_content
    assert data['n_votes'] == 0


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_amount(api_client, default_hearing):
    # list all comments
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))

    data = get_data_from_response(response)
    assert len(data) == 3


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_all_properties(api_client, default_hearing):
    # list all comments
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))
    data = get_data_from_response(response)
    # get first returned comment
    comment = data[0]

    assert 'content' in comment
    assert 'created_at' in comment
    assert 'n_votes' in comment
    assert 'created_by' in comment


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_content(api_client, default_hearing):
    # list all comments
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))

    data = get_data_from_response(response)
    contents = [c['content'] for c in data]

    assert default_comment_content in contents
    assert red_comment_content in contents
    assert green_comment_content in contents


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_votes(api_client, default_hearing):
    # list all comments
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))

    data = get_data_from_response(response)
    for comment in data:
        assert comment['n_votes'] == 0


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_created_by(api_client, default_hearing, john_doe):
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))

    data = get_data_from_response(response)
    for comment in data:
        assert comment['created_by']['username'] == john_doe.username


@pytest.mark.django_db
def test_54_list_all_comments_added_to_hearing_check_created_at(api_client, default_hearing):
    response = api_client.get(get_hearing_detail_url(default_hearing.id, 'comments'))

    data = get_data_from_response(response)
    for comment in data:
        assert_datetime_fuzzy_equal(now(), comment['created_at'])


@pytest.mark.django_db
def test_54_get_hearing_with_comments_check_amount_of_comments(api_client, default_hearing):
    response = api_client.get(get_hearing_detail_url(default_hearing.id))
    data = get_data_from_response(response)
    assert 'comments' in data
    assert len(data['comments']) == 3
    assert data['n_comments'] == 3


@pytest.mark.django_db
def test_54_get_hearing_with_comments_check_comment_properties(api_client, default_hearing):
    response = api_client.get(get_hearing_detail_url(default_hearing.id))

    data = get_data_from_response(response)
    assert 'comments' in data

    # get first comment to check
    comment = data['comments'][0]

    assert 'content' in comment
    assert 'created_at' in comment
    assert 'n_votes' in comment
    assert 'created_by' in comment


@pytest.mark.django_db
def test_56_add_comment_to_section_without_authentication(api_client, default_hearing):
    section = default_hearing.sections.first()
    # post data to section endpoint /v1/hearing/<hearingID>/sections/<sectionID>/comments/
    url = get_hearing_detail_url(default_hearing.id, 'sections/%s/comments' % section.id)
    response = api_client.post(url, data=comment_data)
    assert response.status_code == 201


@pytest.mark.django_db
def test_56_add_comment_to_section_without_data(api_client, default_hearing):
    section = default_hearing.sections.first()
    url = get_hearing_detail_url(default_hearing.id, 'sections/%s/comments' % section.id)
    response = api_client.post(url, data=None)
    # expect bad request, we didn't set any data
    assert response.status_code == 400


@pytest.mark.django_db
def test_56_add_comment_to_section_invalid_key(api_client, default_hearing):
    section = default_hearing.sections.first()
    url = get_hearing_detail_url(default_hearing.id, 'sections/%s/comments' % section.id)
    response = api_client.post(url, data={'invalidKey': 'Yes it is'})
    # expect bad request, we have invalid key in payload
    assert response.status_code == 400


@pytest.mark.django_db
def test_56_add_comment_to_section(john_doe_api_client, default_hearing):
    section = default_hearing.sections.first()
    url = get_hearing_detail_url(default_hearing.id, 'sections/%s/comments' % section.id)

    # set section explicitly
    comment_data['section'] = section.pk
    response = john_doe_api_client.post(url, data=comment_data)

    data = get_data_from_response(response, status_code=201)
    assert 'section' in data
    assert data['section'] == section.pk

    assert 'content' in data
    assert data['content'] == default_comment_content


@pytest.mark.django_db
def test_56_get_hearing_with_section_check_n_comments_property(api_client):
    hearing = Hearing.objects.create(abstract='Hearing to test section comments')
    section = Section.objects.create(title='Section to comment', hearing=hearing, commenting=Commenting.OPEN)
    url = get_hearing_detail_url(hearing.id, 'sections/%s/comments' % section.id)

    comment_data['section'] = section.pk
    response = api_client.post(url, data=comment_data)
    assert response.status_code == 201

    # get hearing and check sections's n_comments property
    url = get_hearing_detail_url(hearing.id)
    response = api_client.get(url)

    data = get_data_from_response(response)
    assert 'n_comments' in data['sections'][0]
    assert data['sections'][0]['n_comments'] == 1


@pytest.mark.django_db
def test_n_comments_updates(admin_user, default_hearing):
    assert Hearing.objects.get(pk=default_hearing.pk).n_comments == 3
    comment = default_hearing.comments.create(created_by=admin_user, content="Hello")
    assert Hearing.objects.get(pk=default_hearing.pk).n_comments == 4
    comment.soft_delete()
    assert Hearing.objects.get(pk=default_hearing.pk).n_comments == 3


@pytest.mark.django_db
def test_comment_edit_versioning(john_doe_api_client, random_hearing):
    random_hearing.commenting = Commenting.OPEN
    random_hearing.save()
    response = john_doe_api_client.post('/v1/hearing/%s/comments/' % random_hearing.pk, data={
        "content": "THIS SERVICE SUCKS"
    })
    data = get_data_from_response(response, 201)
    comment_id = data["id"]
    comment = HearingComment.objects.get(pk=comment_id)
    assert comment.content.isupper()  # Oh my, all that screaming :(
    assert not reversion.get_for_object(comment)  # No revisions
    response = john_doe_api_client.patch('/v1/hearing/%s/comments/%s/' % (random_hearing.pk, comment_id), data={
        "content": "Never mind, it's nice :)"
    })
    data = get_data_from_response(response, 200)
    comment = HearingComment.objects.get(pk=comment_id)
    assert not comment.content.isupper()  # Screaming is gone
    assert len(reversion.get_for_object(comment)) == 1  # One old revision


@pytest.mark.django_db
def test_correct_m2m_fks(admin_user, default_hearing):
    hearing_comment = default_hearing.comments.create(created_by=admin_user, content="hello")
    first_section = default_hearing.sections.first()
    section_comment = first_section.comments.create(created_by=admin_user, content="hello")
    hc_voters_query = force_text(hearing_comment.voters.all().query)
    sc_voters_query = force_text(section_comment.voters.all().query)
    assert "sectioncomment" in sc_voters_query and "hearingcomment" not in sc_voters_query
    assert "hearingcomment" in hc_voters_query and "sectioncomment" not in hc_voters_query


comment_status_spec = {
    Commenting.NONE: (403, 403),
    Commenting.REGISTERED: (403, 201),
    Commenting.OPEN: (201, 201),
}


@pytest.mark.django_db
@pytest.mark.parametrize("commenting", comment_status_spec.keys())
def test_commenting_modes(api_client, john_doe_api_client, commenting):
    hearing = Hearing.objects.create(commenting=commenting)
    anon_status, reg_status = comment_status_spec[commenting]
    response = api_client.post(get_hearing_detail_url(hearing.id, 'comments'), data=comment_data)
    assert response.status_code == anon_status
    response = john_doe_api_client.post(get_hearing_detail_url(hearing.id, 'comments'), data=comment_data)
    assert response.status_code == reg_status
