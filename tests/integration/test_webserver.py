import urllib.request
import urllib.error

import pytest


@pytest.mark.parametrize('path, content, expected', [
    ('/', '<title>httpbin(1): HTTP Client Testing Service</title>', True),
    # https://github.com/Runscope/httpbin/issues/245
    ('/', 'www.google-analytics.com', False),
    ('/data/hello.txt', 'Hello World!', True),
])
def test_httpbin(httpbin, qtbot, path, content, expected):
    with qtbot.waitSignal(httpbin.got_new_url, raising=True, timeout=100):
        url = 'http://localhost:{}{}'.format(httpbin.port, path)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            # "Though being an exception (a subclass of URLError), an HTTPError
            # can also function as a non-exceptional file-like return value
            # (the same thing that urlopen() returns)."
            # ...wat
            print(e.read().decode('utf-8'))
            raise

    data = response.read().decode('utf-8')

    assert httpbin.get_visited() == ['GET {}'.format(path)]
    assert (content in data) == expected
