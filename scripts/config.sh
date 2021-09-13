#!/bin/bash
#
# Set environment variables for the training and testing of stanza modules.

# Set UDBASE to the location of UD data folder
# The data should be CoNLL-U format
# For details, see http://universaldependencies.org/conll18/data.html (CoNLL-18 UD data)
export UDBASE=/Users/jean/Projects/UD_Ligurian-GLT/corpora

# Set NERBASE to the location of NER data folder
# The data should be BIO format
# For details, see https://www.aclweb.org/anthology/W03-0419.pdf (CoNLL-03 NER paper)
# export NERBASE=/path/to/NER

# Set directories to store processed training/evaluation files
export DATA_ROOT=/Users/jean/Projects/stanza/data
export TOKENIZE_DATA_DIR=$DATA_ROOT/tokenize
export MWT_DATA_DIR=$DATA_ROOT/mwt
export LEMMA_DATA_DIR=$DATA_ROOT/lemma
export POS_DATA_DIR=$DATA_ROOT/pos
export DEPPARSE_DATA_DIR=$DATA_ROOT/depparse
export ETE_DATA_DIR=$DATA_ROOT/ete
export NER_DATA_DIR=$DATA_ROOT/ner
export CHARLM_DATA_DIR=$DATA_ROOT/charlm
export SENTIMENT_DATA_DIR=$DATA_ROOT/sentiment

# Set directories to store external word vector data
export WORDVEC_DIR=$DATA_ROOT/extern_data/wordvec
