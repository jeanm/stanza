CORPORA=UD_Ligurian-GLT00
# UD_Ligurian-GLT01 UD_Ligurian-GLT02 UD_Ligurian-GLT03 UD_Ligurian-GLT04 UD_Ligurian-GLT05 UD_Ligurian-GLT06 UD_Ligurian-GLT07 UD_Ligurian-GLT08 UD_Ligurian-GLT09

for corpus in ${CORPORA}; do
    #python -m stanza.utils.datasets.prepare_tokenizer_treebank ${corpus}
    #python -m stanza.utils.datasets.prepare_mwt_treebank ${corpus}
    #python -m stanza.utils.datasets.prepare_pos_treebank ${corpus}
    #python -m stanza.utils.datasets.prepare_lemma_treebank ${corpus}

    #python -m stanza.utils.training.run_tokenizer ${corpus} --steps=1000
    python -m stanza.utils.training.run_mwt ${corpus} --max_steps_before_stop=200 --word_emb_dim=50
    python -m stanza.utils.training.run_pos ${corpus} --wordvec_pretrain_file=/Users/jean/Projects/stanza/saved_models/pos/lij.pretrain.pt
    python -m stanza.utils.training.run_lemma ${corpus}

    python -m stanza.utils.datasets.prepare_depparse_treebank ${corpus}
    python -m stanza.utils.training.run_depparse ${corpus}
done
