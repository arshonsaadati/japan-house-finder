from akiya.browser import looks_like_challenge, looks_blocked


def test_detects_aws_waf_status():
    assert looks_like_challenge("", status=202) is True


def test_detects_challenge_interstitial():
    assert looks_like_challenge("<h1>Let's confirm you are human</h1>") is True


def test_detects_cloudflare_hard_block():
    assert looks_blocked("<title>Attention Required! | Cloudflare</title>") is True
    assert looks_blocked("Sorry, you have been blocked") is True


def test_real_page_is_neither():
    page = "<html><body>" + "<div class='property-card'>house</div>" * 50 + "</body></html>"
    assert looks_like_challenge(page) is False
    assert looks_blocked(page) is False


def test_empty_is_neither():
    assert looks_like_challenge("") is False
    assert looks_blocked("") is False
