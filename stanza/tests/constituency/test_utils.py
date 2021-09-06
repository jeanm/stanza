import pytest

from stanza import Pipeline
from stanza.models.constituency import tree_reader
from stanza.models.constituency import utils

from stanza.tests import *

pytestmark = [pytest.mark.pipeline, pytest.mark.travis]


@pytest.fixture(scope="module")
def pipeline():
    return Pipeline(lang="en", processors="tokenize, pos", tokenize_pretokenized=True)



def test_xpos_retag(pipeline):
    """
    Test using the English tagger that trees will be correctly retagged by read_trees using xpos
    """
    text = "((S (VP (X Find)) (NP (X Mox) (X Opal))))   ((S (NP (X Ragavan)) (VP (X steals) (NP (X important) (X cards)))))"
    expected = "((S (VP (VB Find)) (NP (NNP Mox) (NNP Opal)))) ((S (NP (NNP Ragavan)) (VP (VBZ steals) (NP (JJ important) (NNS cards)))))"

    trees = tree_reader.read_trees(text)

    new_trees = utils.retag_trees(trees, pipeline, xpos=True)
    assert new_trees == tree_reader.read_trees(expected)



def test_upos_retag(pipeline):
    """
    Test using the English tagger that trees will be correctly retagged by read_trees using upos
    """
    text = "((S (VP (X Find)) (NP (X Mox) (X Opal))))   ((S (NP (X Ragavan)) (VP (X steals) (NP (X important) (X cards)))))"
    expected = "((S (VP (VERB Find)) (NP (PROPN Mox) (PROPN Opal)))) ((S (NP (PROPN Ragavan)) (VP (VERB steals) (NP (ADJ important) (NOUN cards)))))"

    trees = tree_reader.read_trees(text)

    new_trees = utils.retag_trees(trees, pipeline, xpos=False)
    assert new_trees == tree_reader.read_trees(expected)
