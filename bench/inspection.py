"""What fastdrf does for each case: compiled output, recognized input, or DRF."""

from django.urls import resolve
from fastdrf.compiler import report_details
from fastdrf.inputs import report_input_details
from fastdrf.settings import fastdrf_settings

from bench.cases import INPUT, WRITE, Case


def serializer_class(case: Case) -> type:
    """The fastdrf profile's serializer class of ``case``'s view."""
    match = resolve(case.path, urlconf="bench.api.fast.urls")
    view = match.func.view_class
    return match.func.view_initkwargs.get("serializer_class", view.serializer_class)


def describe(eligibility) -> str:
    return "compiled" if eligibility.eligible else f"DRF: {eligibility.reason}"


def fastdrf_path(case: Case) -> dict[str, str]:
    """``output`` and ``input``: compiled or recognized by fastdrf, or DRF's and why."""
    backend = fastdrf_settings.SERIALIZER_BACKEND
    cls = serializer_class(case)
    result = {"serializer": cls.__name__}
    if case.kind != INPUT:
        result["output"] = describe(report_details(cls(), backend=backend))
    if case.kind in (INPUT, WRITE):
        if case.status >= 400:
            result["input"] = "DRF: the recognizer does not accept invalid input"
        else:
            eligibility = report_input_details(cls(data={}), backend=backend)
            result["input"] = (
                "recognized" if eligibility.eligible else f"DRF: {eligibility.reason}"
            )
    return result
