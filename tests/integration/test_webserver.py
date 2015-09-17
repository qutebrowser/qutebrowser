import urllib.request

import pytest


@pytest.mark.parametrize('path, content, expected', [
    ('/', '<title>httpbin(1): HTTP Client Testing Service</title>', True),
    # https://github.com/Runscope/httpbin/issues/245
    ('/', 'www.google-analytics.com', False),
    ('/html/hello.html', 'Hello World!', True),
])
def test_httpbin(httpbin, qtbot, path, content, expected):
    with qtbot.waitSignal(httpbin.got_new_url, raising=True, timeout=100):
        url = 'http://localhost:{}{}'.format(httpbin.port, path)
        response = urllib.request.urlopen(url)

    data = response.read().decode('utf-8')

    assert httpbin.get_visited() == ['GET {}'.format(path)]
    assert (content in data) == expected
