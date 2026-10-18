"""Deterministic adversarial partitions for the product's diagnostic core."""
from types import SimpleNamespace

import pytest
from diagnosis_alignment import polynomial_alignment
from fastapi.testclient import TestClient
from inequality_compute import format_solution, grade_inequality, source_inequality
from service import create_app


def records(*texts):
    return [SimpleNamespace(id=f's{i}', text=text) for i, text in enumerate(texts)]


CASES = [(a, root, b) for a in (-4, -2, -1, 1, 2, 4)
         for root in (-5, -1, 0, 1, 5) for b in (-3, 0, 3)]


@pytest.mark.parametrize('a,root,b', CASES)
def test_linear_diagnosis_across_sign_zero_and_coefficient_partitions(a, root, b):
    source = f'解方程：{a}*x+({b})={a*root+b}'
    correct = records(f'{a}*x={a*root}', f'x={root}')
    checked = polynomial_alignment(source, correct, correct, f'x={root}')
    assert checked is not None
    alignment, complete = checked
    assert complete and all(step['math_valid'] for step in alignment)
    assert not any(step['is_first_error'] for step in alignment)


@pytest.mark.parametrize('a,root,b', CASES)
def test_later_correct_answer_never_erases_earlier_wrong_transformation(a, root, b):
    source = f'解方程：{a}*x+({b})={a*root+b}'
    reference = records(f'{a}*x={a*root}', f'x={root}')
    student = records(f'{a}*x={a*root+1}', f'x={root}')
    checked = polynomial_alignment(source, reference, student, f'x={root}')
    assert checked is not None
    alignment, complete = checked
    assert not complete
    assert alignment[0]['is_first_error'] and not alignment[0]['math_valid']
    assert alignment[0]['student_step_id'] == 's0'


@pytest.mark.parametrize('a,root,b', CASES)
def test_matching_steps_never_certify_a_different_final_answer(a, root, b):
    source = f'解方程：{a}*x+({b})={a*root+b}'
    correct = records(f'{a}*x={a*root}', f'x={root}')
    checked = polynomial_alignment(source, correct, correct, f'x={root+1}')
    assert checked is not None and not checked[1]


@pytest.mark.parametrize('field', ['text', 'subject', 'question_type', 'student_answer'])
@pytest.mark.parametrize('value', [True, False, 0, 1.5, [], {}, ['text']])
def test_algorithm_text_fields_reject_non_text_before_model_or_tools(tmp_path, field, value):
    app = create_app(secret='release-'+'x'*32, pool_path=tmp_path/'missing.json')
    with TestClient(app) as client:
        response = client.post('/v1/compute', headers={'Authorization':'Bearer '+'release-'+'x'*32},
                               json={'operation':'analyze', 'text':'解方程：x+1=2', field:value})
        assert response.status_code == 422
        assert 'private' not in response.text


@pytest.mark.parametrize('left,right', [(a,b) for a in range(-3,4) for b in range(-3,4)])
def test_quadratic_all_roots_including_repeated_roots_are_required(left, right):
    question = f'解方程：x^2+({-left-right})*x+({left*right})=0'
    factored = f'(x-({left}))*(x-({right}))=0'
    answer = f'x={left}' if left == right else f'x={left} 或 x={right}'
    work = records(factored, answer)
    checked = polynomial_alignment(question, work, work, answer)
    assert checked is not None and checked[1]
    if left != right:
        incomplete = records(factored, f'x={left}')
        checked = polynomial_alignment(question, work, incomplete, f'x={left}')
        assert checked is not None and not checked[1]
        assert checked[0][1]['is_first_error']


@pytest.mark.parametrize('coefficient', [-4,-1,1,4])
@pytest.mark.parametrize('bound', [-3,0,3])
@pytest.mark.parametrize('operator', ['<','<=','>','>='])
def test_inequality_sign_and_endpoint_variations_must_not_be_confused(coefficient, bound, operator):
    question = f'解不等式：{coefficient}*x{operator}{coefficient*bound}'
    source = source_inequality(question)
    assert source is not None
    reference = format_solution(source)
    result = grade_inequality(question, reference, reference)
    assert result['verdict'] == 'confirmed_correct' and result['can_update_learning']
    actual = operator if coefficient > 0 else {'<':'>','<=':'>=','>':'<','>=':'<='}[operator]
    # Independent oracle: division by a negative coefficient reverses direction.
    result = grade_inequality(question, f'x{actual}{bound}', reference)
    assert result['verdict'] == 'confirmed_correct'
    opposite = {'<':'>','<=':'>=','>':'<','>=':'<='}[actual]
    result = grade_inequality(question, f'x{opposite}{bound}', reference)
    assert result['verdict'] == 'confirmed_incorrect'
    # Change only whether the boundary belongs to the solution, not its direction.
    wrong = {'<':'<=','<=':'<','>':'>=','>=':'>'}[actual]
    result = grade_inequality(question, f'x{wrong}{bound}', reference)
    assert result['verdict'] == 'confirmed_incorrect'
