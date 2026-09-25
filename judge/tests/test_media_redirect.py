from unittest import mock

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from judge.views.widgets import media_redirect


class MediaRedirectTest(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/martor/abc.jpg')

    @mock.patch('judge.views.widgets.default_storage')
    def test_redirects_to_storage_url(self, storage):
        storage.url.return_value = 'https://media.example.com/martor/abc.jpg'

        response = media_redirect(self.request, media_dir='martor', name='abc.jpg')

        storage.url.assert_called_once_with('martor/abc.jpg')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://media.example.com/martor/abc.jpg')

    @mock.patch('judge.views.widgets.default_storage')
    def test_rejects_hidden_and_traversal_names(self, storage):
        for name in ('..', '.env', 'sub/abc.jpg'):
            with self.assertRaises(Http404):
                media_redirect(self.request, media_dir='martor', name=name)
        storage.url.assert_not_called()
