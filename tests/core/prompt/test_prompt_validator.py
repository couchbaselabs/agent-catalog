import pathlib
import pydantic
import pytest
import uuid

from rosetta_core.prompt.models import PromptDescriptorFactory
from rosetta_core.version import VersionDescriptor
from rosetta_core.version.identifier import VersionSystem


def _get_prompt_descriptor_factory(cls, filename: pathlib.Path):
    filename_prefix = pathlib.Path(__file__).parent / "resources"
    factory_args = {
        "filename": filename_prefix / filename,
        "version": VersionDescriptor(identifier=uuid.uuid4().hex, version_system=VersionSystem.Raw),
    }
    return cls(**factory_args)


@pytest.mark.smoke
def test_raw_prompt():
    positive_1_factory = _get_prompt_descriptor_factory(
        cls=PromptDescriptorFactory, filename=pathlib.Path("positive_1.prompt")
    )
    positive_1_prompts = list(positive_1_factory)
    assert len(positive_1_prompts) == 1
    assert positive_1_prompts[0].name == "route_finding_prompt"
    assert "Instructions on how to find routes between airports." in positive_1_prompts[0].description
    assert isinstance(positive_1_prompts[0].annotations, dict)
    assert len(positive_1_prompts[0].annotations) == 1
    assert "organization" in positive_1_prompts[0].annotations
    assert positive_1_prompts[0].annotations["organization"] == "sequoia"
    assert (
        "Goal:\nYour goal is to find a sequence of routes between the source and destination airport."
        in positive_1_prompts[0].prompt
    )
    assert len(positive_1_prompts[0].tools) == 2
    assert positive_1_prompts[0].tools[0].name == "find_direct_routes"
    assert positive_1_prompts[0].tools[0].annotations == 'gdpr_2016_compliant = "true"'
    assert positive_1_prompts[0].tools[0].limit == 1
    assert positive_1_prompts[0].tools[1].query == "finding routes"
    assert positive_1_prompts[0].tools[1].limit == 2

    # Test the optional exclusion of tools and annotations.
    positive_2_factory = _get_prompt_descriptor_factory(
        cls=PromptDescriptorFactory, filename=pathlib.Path("positive_2.prompt")
    )
    positive_2_prompts = list(positive_2_factory)
    assert len(positive_2_prompts) == 1
    assert positive_2_prompts[0].name == "route_finding_prompt"
    assert positive_2_prompts[0].annotations is None
    assert positive_2_prompts[0].tools is None

    # Test a bad record_kind (not raw_prompt).
    negative_1_factory = _get_prompt_descriptor_factory(
        cls=PromptDescriptorFactory, filename=pathlib.Path("negative_1.prompt")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_1_factory)

    # Test a bad annotation query string.
    negative_2_factory = _get_prompt_descriptor_factory(
        cls=PromptDescriptorFactory, filename=pathlib.Path("negative_2.prompt")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_2_factory)
