Tests in this directory are automatically picked up by `test_hints` in
`tests/end2end/test_hints_html.py`.

They need to contain a special `<!-- target: foo.html -->` comment which
specifies where the hint in it will point to, and will then test that.
