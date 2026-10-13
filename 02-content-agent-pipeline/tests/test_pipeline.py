import pytest

from pipeline import collect, generate

RSS = b"""<rss><channel><item><title>A &amp; B</title><link>https://x/1</link>
<description>&lt;b&gt;bold&lt;/b&gt;   text</description></item>
<item><title></title><link>https://x/2</link></item></channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>
<link href="https://y/1"/><summary>S</summary></entry></feed>"""


def test_rss_parsed_and_cleaned():
    items = collect.parse_feed(RSS, "src")
    assert items == [{"title": "A & B", "link": "https://x/1", "summary": "bold text", "source": "src"}]


def test_atom_parsed():
    assert collect.parse_feed(ATOM, "a")[0]["link"] == "https://y/1"


def test_reply_with_markdown_fence():
    raw = '```json\n{"title":"t","text":"x","hashtags":["a"],"image_prompt":"p"}\n```'
    assert generate.parse_reply(raw)["title"] == "t"


@pytest.mark.parametrize("raw", ["not json", '{"title": "t"}'])
def test_bad_reply_raises(raw):
    with pytest.raises(generate.GenerationError):
        generate.parse_reply(raw)


def test_format_post_hashtags():
    post = {"title": "T", "text": "X", "hashtags": ["#a", "b"], "image_prompt": ""}
    assert generate.format_post(post, "https://l").endswith("#a #b")
