from app.card_resolution.scoring import Candidate, Evidence, decide, retrieve_candidates


def _charizard(**overrides) -> dict:
    payload = {
        "game": "pokemon",
        "name": "Charizard",
        "set_name": "Base Set",
        "set_code": "BS",
        "collector_number": "4",
        "language": "EN",
        "printing": "Non-Holo",
    }
    payload.update(overrides)
    return payload


def _candidate(shop="shop-a", **overrides) -> Candidate:
    data = _charizard()
    data.update(overrides)
    return Candidate(shop_id=shop, **{k: data.get(k) for k in (
        "game",
        "name",
        "set_name",
        "set_code",
        "collector_number",
        "language",
        "printing",
        "justtcg_id",
        "tcgplayer_id",
    )})


def test_e1_unique_exact_accepts():
    evidence = Evidence.from_payload(_charizard())
    decision = decide(evidence, [_candidate()])
    assert decision.result == "accepted"
    assert decision.identity_confidence_hundredths == 100
    assert decision.winner.total == 100


def test_e2_mapped_printing_makes_holo_ineligible():
    evidence = Evidence.from_payload(_charizard())
    holo = _candidate(printing="Holo", collector_number="4")
    decision = decide(evidence, [_candidate(), holo])
    assert decision.result == "accepted"
    assert len([row for row in decision.scored if row.eligible]) == 1


def test_e3_omitted_printing_abstains():
    evidence = Evidence.from_payload(_charizard(printing=None))
    decision = decide(evidence, [_candidate(), _candidate(printing="Holo")])
    assert decision.result == "abstained"
    assert "omitted_printing" in decision.reason_codes


def test_e4_fuzzy_name_retrieves_but_cannot_accept():
    evidence = Evidence.from_payload(_charizard(name="Charzard"))
    catalog = [_candidate(), _candidate(collector_number="6", name="Charizard")]
    merged, codes = retrieve_candidates(catalog, [], "shop-a")
    assert not codes
    decision = decide(evidence, merged)
    assert decision.result == "abstained"
    assert all(row.total < 100 for row in decision.scored)


def test_e5_price_does_not_change_identity():
    evidence = Evidence.from_payload(_charizard(price=999))
    decision = decide(evidence, [_candidate()])
    assert decision.result == "accepted"
    assert decision.identity_confidence_hundredths == 100


def test_e6_name_number_conflict_abstains():
    evidence = Evidence.from_payload(_charizard(name="Blastoise"))
    decision = decide(evidence, [_candidate()])
    assert decision.result == "abstained"
    assert decision.result != "accepted"


def test_e7_unsupported_game_rejects():
    evidence = Evidence.from_payload(_charizard(game="one piece"))
    decision = decide(evidence, [_candidate(game="one piece")])
    assert decision.result == "rejected"
    assert "unsupported_game" in decision.reason_codes


def test_e8_missing_game_rejects():
    evidence = Evidence.from_payload(_charizard(game=None))
    decision = decide(evidence, [_candidate()])
    assert decision.result == "rejected"
    assert "missing_game" in decision.reason_codes


def test_e9_game_mismatch_rejects():
    evidence = Evidence.from_payload(_charizard())
    decision = decide(evidence, [_candidate(game="one piece", name="Luffy")])
    assert decision.result == "rejected"
    assert "game_mismatch" in decision.reason_codes


def test_e10_empty_body_rejects():
    evidence = Evidence.from_payload({})
    decision = decide(evidence, [])
    assert decision.result == "rejected"
    assert "missing_game" in decision.reason_codes


def test_e12_duplicate_canonical_identity_abstains():
    evidence = Evidence.from_payload(_charizard())
    decision = decide(evidence, [_candidate(row_id="1"), _candidate(row_id="2")])
    assert decision.result == "abstained"
    assert "duplicate_canonical_identity" in decision.reason_codes


def test_e14_unmapped_printing_abstains():
    evidence = Evidence.from_payload(_charizard(printing="shiny"))
    decision = decide(evidence, [_candidate(), _candidate(printing="Holo")])
    assert decision.result == "abstained"


def test_identifier_conflict_abstains():
    evidence = Evidence.from_payload(_charizard(justtcg_id="j-1", tcgplayer_id="t-2"))
    left = _candidate(justtcg_id="j-1", tcgplayer_id="t-1")
    right = _candidate(
        name="Blastoise",
        collector_number="2",
        justtcg_id="j-2",
        tcgplayer_id="t-2",
    )
    decision = decide(evidence, [left, right])
    assert decision.result == "abstained"
    assert "identifier_conflict" in decision.reason_codes


def test_advisory_confidence_cannot_accept():
    evidence = Evidence.from_payload(_charizard(name="Charzard", model_confidence=0.99))
    decision = decide(evidence, [_candidate()])
    assert decision.result != "accepted"
