"""A repair proposal is not a proof merely because it repeats model reference prose."""
import asyncio

import pytest
from app.schemas import CounterfactualRepairProposal, DiagnosisOutput
from app.services.counterfactual import _same_step, validate_first_error_counterfactual


class ProposalProvider:
    def __init__(self, repaired):
        self.repaired = repaired

    async def generate_structured(self, *args, **kwargs):
        return CounterfactualRepairProposal(corrected_first_step=self.repaired[1],
                                            repaired_steps=self.repaired, confidence=0.9)


@pytest.mark.parametrize('confidence', [-0.1,1.1,float('nan'),float('inf'),float('-inf'),True,False,'0.9',[],{},None])
def test_model_diagnosis_confidence_must_be_a_finite_probability(confidence):
    with pytest.raises(ValueError):
        DiagnosisOutput(confidence=confidence)


@pytest.mark.parametrize('confidence', [0,0.25,1])
def test_valid_probability_boundaries_remain_supported(confidence):
    assert DiagnosisOutput(confidence=confidence).confidence == confidence


@pytest.mark.parametrize('left,right', [('I=0.2A','I=02A'),('x=1,2','x=12'),('R=1','r=1')])
def test_repair_comparison_preserves_decimals_separators_and_variable_case(left,right):
    assert not _same_step(left,right)


def test_non_symbolic_reference_agreement_does_not_claim_sympy_or_confirm_cause():
    alignment = [
        {'index':0, 'student_text':'电压为6V', 'reference_text':'电压为6V', 'equivalent':True},
        {'index':1, 'student_text':'电阻用电压乘电流', 'reference_text':'电阻用电压除以电流',
         'equivalent':False, 'is_first_error':True},
    ]
    result = asyncio.run(validate_first_error_counterfactual(
        ProposalProvider(['电压为6V','电阻用电压除以电流']),
        question_text='已知电压和电流，求电阻', subject='物理', alignment=alignment))
    assert 'sympy' not in result['verification_method']
    assert not result['root_cause_confirmed']
    assert result['reference_consistent'] and result['preserved_prefix']


def test_rewriting_a_correct_prefix_cannot_be_confirmed_even_if_later_steps_match():
    alignment = [
        {'index':0, 'student_text':'x+1=2', 'reference_text':'x+1=2', 'equivalent':True},
        {'index':1, 'student_text':'x=3', 'reference_text':'x=1',
         'equivalent':False, 'is_first_error':True},
    ]
    result = asyncio.run(validate_first_error_counterfactual(
        ProposalProvider(['x+1=9','x=1']),
        question_text='解方程：x+1=2', subject='数学', alignment=alignment))
    assert not result['root_cause_confirmed']
    assert not result['preserved_prefix']


def test_symbolically_checked_and_preserved_repair_keeps_its_evidence():
    alignment = [
        {'index':0, 'student_text':'x+1=2', 'reference_text':'x+1=2', 'equivalent':True},
        {'index':1, 'student_text':'x=3', 'reference_text':'x=1',
         'equivalent':False, 'is_first_error':True},
    ]
    result = asyncio.run(validate_first_error_counterfactual(
        ProposalProvider(['x+1=2','x=1']),
        question_text='解方程：x+1=2', subject='数学', alignment=alignment))
    assert result['root_cause_confirmed'] and result['preserved_prefix']
    assert 'sympy' in result['verification_method']
