from sczx_api.question_detail import asset_crop, safe_counterfactual


def test_crop_invalid_and_first_crop_selection():
    assert asset_crop([{'kind': 'crop', 'bbox': [-.1, .2, .8, .9]}]) is None
    assert asset_crop([{'kind': 'crop', 'bbox': [0, 0, 1]}]) is None
    assert asset_crop([{'kind': 'original', 'bbox': []}]) is None


def test_counterfactual_legacy_and_corrected_step():
    old = {'verification_method': 'qwen_proposal_sympy_check', 'root_cause_confirmed': True}
    result = safe_counterfactual(old, {})
    assert result['legacy_review_required'] is True
    assert result['root_cause_confirmed'] is False and result['confidence'] == .5
    current = {'verification_method': 'sympy_check', 'validation_scope': 'prefix', 'suspected_step': 1, 'root_cause_confirmed': True}
    corrected = safe_counterfactual(current, {'user_confirmed': True, 'first_error_step': 2})
    assert corrected['stale_after_correction'] is True
    assert corrected['verification_method'] == 'previous_diagnosis_evidence'
    assert safe_counterfactual(None, {}) is None
