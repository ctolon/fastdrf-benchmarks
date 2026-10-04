"""
Both profiles in this process, each through its own URLconf: every case
answers bench/expected.json's status, headers and bytes, with the same SQL.
"""

from unittest import mock

import pytest

from bench import inprocess, verify
from bench.cases import CASES, INPUT, OUTPUT

URLCONFS = {"drf": "bench.api.drf.urls", "fastdrf": "bench.api.fast.urls"}
EXPECTED = verify.load_expected()
# The cases whose output fastdrf leaves to DRF, by design.
OUTPUT_ON_DRF = {"plain-serializer"}


def run(settings, profile, case):
    settings.ROOT_URLCONF = URLCONFS[profile]
    return inprocess.run(case)


def test_every_case_has_an_expectation():
    assert set(EXPECTED) == set(CASES)


@pytest.mark.django_db
@pytest.mark.parametrize("name", CASES)
def test_profiles_answer_the_expected_bytes(settings, name):
    case = CASES[name]
    drf = run(settings, "drf", case)
    fast = run(settings, "fastdrf", case)
    verify.compare(case, drf.fingerprint, EXPECTED[name])
    verify.compare(case, fast.fingerprint, EXPECTED[name])
    assert drf.fingerprint["status"] == case.status


@pytest.mark.django_db
@pytest.mark.parametrize("name", [n for n, c in CASES.items() if c.uses_database])
def test_profiles_run_the_same_sql(settings, name):
    case = CASES[name]
    drf = run(settings, "drf", case)
    fast = run(settings, "fastdrf", case)
    assert drf.queries == fast.queries == case.queries
    assert drf.statements == fast.statements


@pytest.mark.django_db
@pytest.mark.parametrize("name", [n for n, c in CASES.items() if not c.uses_database])
def test_no_sql_without_a_database(settings, name):
    for profile in URLCONFS:
        assert run(settings, profile, CASES[name]).queries == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [n for n, c in CASES.items() if c.kind != INPUT and n not in OUTPUT_ON_DRF],
)
def test_fastdrf_output_is_compiled(settings, name):
    # With "error", output that is not compiled raises instead of falling
    # back to DRF: these responses come from compiled encoders.
    settings.FASTDRF = {**settings.FASTDRF, "SERIALIZER_BACKEND_FALLBACK": "error"}
    result = run(settings, "fastdrf", CASES[name])
    verify.compare(CASES[name], result.fingerprint, EXPECTED[name])


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(OUTPUT_ON_DRF))
def test_fastdrf_leaves_these_outputs_to_drf(settings, name):
    settings.FASTDRF = {**settings.FASTDRF, "SERIALIZER_BACKEND_FALLBACK": "error"}
    settings.ROOT_URLCONF = URLCONFS["fastdrf"]
    with pytest.raises(Exception, match="cannot use the msgspec backend"):
        inprocess.run(CASES[name])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", [n for n, c in CASES.items() if c.kind == INPUT and c.status == 200]
)
def test_fastdrf_recognizes_valid_input(settings, name):
    from fastdrf import inputs

    results = []
    original = inputs.recognize

    def recognize(*args, **kwargs):
        results.append(original(*args, **kwargs))
        return results[-1]

    with mock.patch.object(inputs, "recognize", recognize):
        run(settings, "fastdrf", CASES[name])
    assert results
    assert all(result is not inputs.NOT_RECOGNIZED for result in results)


def test_inspection_reports_each_case():
    from bench.inspection import fastdrf_path

    for name, case in CASES.items():
        path = fastdrf_path(case)
        if case.kind == OUTPUT:
            assert (path["output"] == "compiled") == (name not in OUTPUT_ON_DRF), path
        if case.kind == INPUT and case.status == 200:
            assert path["input"] == "recognized", path


@pytest.mark.django_db
def test_method_field_can_still_be_measured_without_delegation(settings):
    settings.FASTDRF = {**settings.FASTDRF, "DELEGATE_FIELDS": False}
    result = run(settings, "fastdrf", CASES["method-field"])
    verify.compare(CASES["method-field"], result.fingerprint, EXPECTED["method-field"])
    from bench.inspection import fastdrf_path

    path = fastdrf_path(CASES["method-field"])
    assert path["output"].startswith("DRF:")
    assert path["delegated"] == []


def test_inspection_records_delegated_fields():
    from bench.inspection import fastdrf_path

    assert fastdrf_path(CASES["method-field"])["delegated"] == ["label"]
