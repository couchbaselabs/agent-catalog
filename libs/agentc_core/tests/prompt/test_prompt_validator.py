import datetime
import pathlib
import pydantic
import pytest
import uuid

from agentc_core.prompt.models import PromptDescriptor
from agentc_core.version import VersionDescriptor
from agentc_core.version.identifier import VersionSystem


def _get_prompt_descriptors_factory(cls, filename: pathlib.Path):
    filename_prefix = pathlib.Path(__file__).parent / "resources"
    factory_args = {
        "filename": filename_prefix / filename,
        "version": VersionDescriptor(
            identifier=uuid.uuid4().hex,
            version_system=VersionSystem.Raw,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        ),
    }
    return cls(**factory_args)


@pytest.mark.smoke
def test_prompt():
    positive_1_factory = _get_prompt_descriptors_factory(
        cls=PromptDescriptor.Factory, filename=pathlib.Path("positive_1.yaml")
    )
    positive_1_inputs = list(positive_1_factory)
    assert len(positive_1_inputs) == 1
    assert positive_1_inputs[0].name == "route_finding_prompt"
    assert "Instructions on how to find routes between airports." in positive_1_inputs[0].description
    assert isinstance(positive_1_inputs[0].annotations, dict)
    assert len(positive_1_inputs[0].annotations) == 1
    assert "organization" in positive_1_inputs[0].annotations
    assert positive_1_inputs[0].annotations["organization"] == "sequoia"
    assert isinstance(positive_1_inputs[0].content, dict)
    assert "Goal" in positive_1_inputs[0].content
    assert "Examples" in positive_1_inputs[0].content
    assert "Instructions" in positive_1_inputs[0].content
    assert (
        "Your goal is to find a sequence of routes between the source and destination airport."
        in positive_1_inputs[0].content["Goal"]
    )
    assert len(positive_1_inputs[0].tools) == 2
    assert positive_1_inputs[0].tools[0].name == "find_direct_routes"
    assert positive_1_inputs[0].tools[0].annotations == 'gdpr_2016_compliant = "true"'
    assert positive_1_inputs[0].tools[0].limit == 1
    assert positive_1_inputs[0].tools[1].query == "finding routes"
    assert positive_1_inputs[0].tools[1].limit == 2

    # Test the optional exclusion of tools and annotations.
    positive_2_factory = _get_prompt_descriptors_factory(
        cls=PromptDescriptor.Factory, filename=pathlib.Path("positive_2.yaml")
    )
    positive_2_inputs = list(positive_2_factory)
    assert len(positive_2_inputs) == 1
    assert positive_2_inputs[0].name == "route_finding_prompt"
    assert positive_2_inputs[0].annotations is None
    assert positive_2_inputs[0].tools is None

    # Test a bad record_kind (not raw_prompt).
    negative_1_factory = _get_prompt_descriptors_factory(
        cls=PromptDescriptor.Factory, filename=pathlib.Path("negative_1.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_1_factory)

    # Test a bad annotation query string.
    negative_2_factory = _get_prompt_descriptors_factory(
        cls=PromptDescriptor.Factory, filename=pathlib.Path("negative_2.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_2_factory)
