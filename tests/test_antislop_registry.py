"""Tests for the anti-slop registry and validator.

Regression corpus: known violations and clean text to verify detect() and score()
match expected behavior across all three tiers.
"""

from nio.core.antislop import detect, score, RULES


# --- Registry structure ---

def test_rules_baked_in():
    assert len(RULES) == 27, f"Expected 27 baked-in regex rules, got {len(RULES)}"


def test_all_rules_have_required_fields():
    for rule in RULES:
        assert "id" in rule
        assert "tier" in rule
        assert "pattern" in rule
        assert "severity" in rule
        assert rule["tier"] in ("critical", "context", "natural")


# --- Clean text ---

def test_clean_text_scores_100():
    text = "I built a scoring model in SQLite. It runs every hour and updates the dashboard."
    assert score(text) == 100.0
    assert detect(text) == []


def test_clean_technical_text():
    text = "The pipeline pulls from 3 enrichment sources, scores ICP fit, and pushes to HubSpot."
    assert score(text) == 100.0


# --- Critical tier: em-dashes and en-dashes ---

def test_em_dash_detected():
    text = "I built it \u2014 and it worked \u2014 somehow."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "em_dashes" in ids
    em = next(d for d in detections if d["id"] == "em_dashes")
    assert em["count"] == 2
    assert em["tier"] == "critical"


def test_en_dash_detected():
    text = "Monday \u2013 Friday schedule."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "en_dashes" in ids


# --- Critical tier: authority signaling ---

def test_authority_signaling():
    texts = [
        "The uncomfortable truth about GTM is nobody reads your emails.",
        "Let me be clear: this approach works.",
        "Here's what nobody tells you about cron jobs.",
        "The hard truth is most SDRs quit too early.",
        "Here's the reality of outbound in 2026.",
        "What most people miss is the scoring layer.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "authority_signaling" in ids, f"Failed to detect authority signaling in: {text}"


# --- Critical tier: narrator setup ---

def test_narrator_setup():
    texts = [
        "Here's the thing about enrichment tables.",
        "Here's where it gets interesting.",
        "Here's the real value of this approach.",
        "The real story is in the data.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "narrator_setup" in ids, f"Failed to detect narrator setup in: {text}"


# --- Critical tier: dramatic rhetorical ---

def test_dramatic_rhetorical():
    texts = [
        "But here's the part where everything changed.",
        "And that's when it clicked.",
        "Want to know the crazy part?",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "dramatic_rhetorical" in ids, f"Failed to detect dramatic rhetorical in: {text}"


# --- Critical tier: hype words ---

def test_hype_words():
    texts = [
        "This tool is a game changer.",
        "Unleash your pipeline potential.",
        "A next-level approach to scoring.",
        "This will supercharge your outbound.",
        "Total chaos in the CRM.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "hype_words" in ids, f"Failed to detect hype word in: {text}"


# --- Critical tier: disclaimers and filler ---

def test_no_fluff_disclaimers():
    texts = [
        "No fluff, just tactics.",
        "No BS guide to SQLite.",
        "No nonsense approach.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "no_fluff_disclaimers" in ids, f"Failed to detect no-fluff disclaimer in: {text}"


def test_nada_filler():
    text = "No templates, nada."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "nada_filler" in ids


def test_sycophantic_openers():
    texts = [
        "Great question! Here's how I did it.",
        "Absolutely! The way I see it is...",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "sycophantic_openers" in ids, f"Failed to detect sycophantic opener in: {text}"


def test_humble_brag():
    text = "I don't have all the answers, but here's what worked."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "humble_brag" in ids


def test_self_branded_concepts():
    text = "This is what I call the signal stack."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "self_branded_concepts" in ids


def test_bookend_summary():
    texts = [
        "In summary, the pipeline works.",
        "In conclusion, we shipped it.",
        "In short, it saves 4 hours per week.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "bookend_summary" in ids, f"Failed to detect bookend summary in: {text}"


def test_hedging_transitions():
    text = "That said, the tool works well for most use cases."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "hedging_transitions" in ids


def test_filler_transitions():
    text = "Without further ado, here's the workflow."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "filler_transitions" in ids


def test_false_drama_ellipsis():
    text = "I tried everything... and then it worked."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "false_drama_ellipsis" in ids


def test_self_referential_openers():
    texts = [
        "Dropping this resource for anyone who needs it.",
        "Sharing something I built last week.",
    ]
    for text in texts:
        detections = detect(text)
        ids = [d["id"] for d in detections]
        assert "self_referential_openers" in ids, f"Failed to detect self-referential opener in: {text}"


# --- Context tier ---

def test_engagement_bait():
    text = "So here's my question for you: what's your stack?"
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "engagement_bait" in ids


def test_false_dichotomies():
    text = "It's not luck, it's strategy."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "false_dichotomies" in ids


def test_quotation_overuse():
    text = 'I call this a "growth loop" that compounds.'
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "quotation_overuse" in ids


# --- Natural tier (should detect but NOT penalize) ---

def test_natural_patterns_no_penalty():
    text = "Here's how I set it up... scrape --> score --> notify"
    s = score(text)
    assert s == 100.0, f"Natural patterns should not penalize. Got score {s}"

    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "ellipses_trailing" in ids
    assert "workflow_arrows" in ids
    assert "directional_heres" in ids


def test_directional_heres_not_penalized():
    text = "Here's how to build a scoring model in SQLite from scratch."
    assert score(text) == 100.0


def test_directional_heres_vs_narrator_setup():
    """directional_heres (natural) should NOT trigger narrator_setup (critical)."""
    text = "Here's how I did it."
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "directional_heres" in ids
    # Should not trigger narrator_setup since "here's how" is natural
    assert "narrator_setup" not in ids


# --- Score formula ---

def test_score_penalizes_critical_more_than_context():
    critical_text = "The uncomfortable truth is nobody reads your emails."
    context_text = "So here's my question for you: what do you think?"
    assert score(critical_text) < score(context_text)


def test_score_clamps_to_zero():
    """Multiple heavy violations in short text should clamp to 0, not go negative."""
    text = "Game changer \u2014 unleash \u2014 supercharge \u2014 chaos."
    assert score(text) == 0.0


def test_score_proportional_to_length():
    """Same violation in longer text should score higher (less penalty per token)."""
    short = "This game changer works."
    long = "I built a full data pipeline with SQLite tables, webhook handlers, automated scoring, and dashboard sync. This game changer of a workflow saves 4 hours a day."
    assert score(long) > score(short)


# --- Multi-violation regression ---

def test_multi_violation_sloppy_text():
    """Classic AI-generated slop should trigger multiple detections."""
    text = (
        "The uncomfortable truth is that most GTM teams are stuck. "
        "Let me be clear \u2014 this is a game changer. "
        "Here's where it gets interesting. "
        "No fluff, just tactics. Nada."
    )
    detections = detect(text)
    ids = [d["id"] for d in detections]
    assert "authority_signaling" in ids
    assert "em_dashes" in ids
    assert "hype_words" in ids
    assert "narrator_setup" in ids
    assert "no_fluff_disclaimers" in ids
    assert "nada_filler" in ids
    assert score(text) < 20.0, "Heavily sloppy text should score very low"
