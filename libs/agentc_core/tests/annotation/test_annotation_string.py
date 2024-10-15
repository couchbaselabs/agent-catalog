import pytest

from agentc_core.annotation import AnnotationPredicate


@pytest.mark.smoke
def test_annotation_predicate():
    positive1 = AnnotationPredicate('key="value"')
    assert len(positive1.disjuncts) == 1
    assert positive1.disjuncts[0] == {"key": "value"}
    assert len(positive1.operators) == 0

    positive2 = AnnotationPredicate(' key =   "value"    ')
    assert len(positive2.disjuncts) == 1
    assert positive2.disjuncts[0] == {"key": "value"}
    assert len(positive2.operators) == 0

    positive3 = AnnotationPredicate(' key1 = "value1" AND key2 = "value2" ')
    assert len(positive3.disjuncts) == 1
    assert positive3.disjuncts[0] == {"key1": "value1", "key2": "value2"}
    assert len(positive3.operators) == 1

    positive4 = AnnotationPredicate(' "value1" = key1 AND "value2" = key2 ')
    assert len(positive4.disjuncts) == 1
    assert positive4.disjuncts[0] == {"key1": "value1", "key2": "value2"}
    assert len(positive4.operators) == 1

    positive5 = AnnotationPredicate(' key1 = "value1" AND key2 = "value2" AND key3 = "value3" ')
    assert len(positive5.disjuncts) == 1
    assert positive5.disjuncts[0] == {"key1": "value1", "key2": "value2", "key3": "value3"}
    assert len(positive5.operators) == 2

    positive6 = AnnotationPredicate(' key1 = "value1" OR key2 = "value2" ')
    assert len(positive6.disjuncts) == 2
    assert positive6.disjuncts[0] == {"key1": "value1"}
    assert positive6.disjuncts[1] == {"key2": "value2"}
    assert len(positive6.operators) == 1

    positive7 = AnnotationPredicate('key1 = "value1" OR key2 = "value2" OR key3 = "value3"')
    assert len(positive7.disjuncts) == 3
    assert positive7.disjuncts[0] == {"key1": "value1"}
    assert positive7.disjuncts[1] == {"key2": "value2"}
    assert positive7.disjuncts[2] == {"key3": "value3"}
    assert len(positive7.operators) == 2

    positive8 = AnnotationPredicate('key1 = "value1" OR key2 = "value2" AND key3 = "value3"')
    assert len(positive8.disjuncts) == 2
    assert positive8.disjuncts[0] == {"key1": "value1"}
    assert positive8.disjuncts[1] == {"key2": "value2", "key3": "value3"}
    assert len(positive8.operators) == 2

    positive9 = AnnotationPredicate('key1 = "value1" AND key2 = "value2" OR key3 = "value3"')
    assert len(positive9.disjuncts) == 2
    assert positive9.disjuncts[0] == {"key1": "value1", "key2": "value2"}
    assert positive9.disjuncts[1] == {"key3": "value3"}
    assert len(positive9.operators) == 2

    positive10 = AnnotationPredicate('key1 = "value1" AND key2 = "value2" OR key3 = "value3" AND key4 = "value4"')
    assert len(positive10.disjuncts) == 2
    assert positive10.disjuncts[0] == {"key1": "value1", "key2": "value2"}
    assert positive10.disjuncts[1] == {"key3": "value3", "key4": "value4"}
    assert len(positive10.operators) == 3

    # Test without a value.
    with pytest.raises(ValueError):
        AnnotationPredicate("key")

    # Test without a key.
    with pytest.raises(ValueError):
        AnnotationPredicate('"value"')

    # Test potential SQL++ injection.
    with pytest.raises(ValueError):
        AnnotationPredicate("; DROP SCOPE myscope.mycollection;")

    # Test invalid value format.
    with pytest.raises(ValueError):
        AnnotationPredicate("key=value")
