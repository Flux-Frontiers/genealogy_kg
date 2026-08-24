"""Tests for genealogy_kg.lineage against the fixture GEDCOM."""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_kg.lineage import ancestors, ascii_tree, descendants, kinship_path
from genealogy_kg.module import GenealogyKG


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


def test_ancestors_nearest_generation_first(built_kg: GenealogyKG) -> None:
    result = ancestors(built_kg.store, "person:I12", generations=4)
    by_gen = {n["id"]: n["generation"] for n in result}
    assert by_gen["person:I7"] == 1  # father
    assert by_gen["person:I11"] == 1  # mother
    assert by_gen["person:I3"] == 2  # grandfather
    assert by_gen["person:I1"] == 3  # great-grandfather


def test_ancestors_stop_when_generations_exhausted(built_kg: GenealogyKG) -> None:
    result = ancestors(built_kg.store, "person:I12", generations=1)
    assert {n["id"] for n in result} == {"person:I7", "person:I11"}


def test_descendants_nearest_generation_first(built_kg: GenealogyKG) -> None:
    result = descendants(built_kg.store, "person:I1", generations=4)
    by_gen = {n["id"]: n["generation"] for n in result}
    assert by_gen["person:I3"] == 1  # son
    assert by_gen["person:I7"] == 2  # grandson
    assert by_gen["person:I12"] == 3  # great-granddaughter


def test_ancestors_of_a_root_person_is_empty(built_kg: GenealogyKG) -> None:
    assert ancestors(built_kg.store, "person:I1", generations=4) == []


def test_kinship_path_between_great_grandchild_and_ancestor(built_kg: GenealogyKG) -> None:
    path = kinship_path(built_kg.store, "person:I12", "person:I1")
    ids = [step["id"] for step in path if "id" in step]
    assert ids[0] == "person:I12"
    assert ids[-1] == "person:I1"
    relations = [step["relation"] for step in path if "relation" in step]
    assert relations == ["child of", "child of", "child of"]


def test_kinship_path_same_person(built_kg: GenealogyKG) -> None:
    path = kinship_path(built_kg.store, "person:I1", "person:I1")
    assert len(path) == 1
    assert path[0]["id"] == "person:I1"


def test_kinship_path_to_unknown_person_is_empty(built_kg: GenealogyKG) -> None:
    assert kinship_path(built_kg.store, "person:I5", "person:does-not-exist") == []


def test_kinship_path_from_unknown_person_is_empty(built_kg: GenealogyKG) -> None:
    assert kinship_path(built_kg.store, "person:does-not-exist", "person:I5") == []


def test_ascii_tree_descendants_shows_spouses_and_lifespans(built_kg: GenealogyKG) -> None:
    tree = ascii_tree(built_kg.store, "person:I1", direction="descendants", generations=4)
    text = str(tree)
    assert text.startswith("John Hartwell (1820-1891) m. Mary Ashcombe")
    assert "+-- William Hartwell (1848-1922) m. Anna Kessler" in text
    assert "`-- Thomas Hartwell (1855-1857)" in text
    assert repr(tree) == text  # __repr__ and __str__ agree


def test_ascii_tree_ancestors_direction(built_kg: GenealogyKG) -> None:
    tree = ascii_tree(built_kg.store, "person:I12", direction="ancestors", generations=4)
    text = str(tree)
    assert text.startswith("Margaret Hartwell (1903-1990)")
    assert "Robert Hartwell (1876-1949) m. Louise Brandt" in text
    assert "John Hartwell (1820-1891) m. Mary Ashcombe" in text


def test_ascii_tree_unknown_person(built_kg: GenealogyKG) -> None:
    tree = ascii_tree(built_kg.store, "person:does-not-exist")
    assert "no such person" in str(tree)


def test_ascii_tree_rejects_bad_direction(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="direction"):
        ascii_tree(built_kg.store, "person:I1", direction="sideways")
