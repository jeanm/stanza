"""A command line interface to a shift reduce constituency parser.

This follows the work of
Recurrent neural network grammars by Dyer et al
In-Order Transition-based Constituent Parsing by Liu & Zhang

The general outline is:

  Train a model by taking a list of trees, converting them to
    transition sequences, and learning a model which can predict the
    next transition given a current state
  Then, at inference time, repeatedly predict the next transition until parsing is complete

The "transitions" are variations on shift/reduce as per an
intro-to-compilers class.  The idea is that you can treat all of the
words in a sentence as a buffer of tokens, then either "shift" them to
represent a new constituent, or "reduce" one or more constituents to
form a new constituent.

In order to make the runtime a more competitive speed, effort is taken
to batch the transitions and apply multiple transitions at once.  At
train time, batches are groups together by length, and at inference
time, new trees are added to the batch as previous trees on the batch
finish their inference.

There are two minor differences in the model:
  - The word input is a bi-lstm, not a uni-lstm.
    This gave a small increase in accuracy.
  - The combination of several constituents into one constituent is done
    via a single bi-lstm rather than two separate lstms.  This increases
    speed without a noticeable effect on accuracy.

The code breakdown is as follows:

  this file: main interface for training or evaluating models
  constituency/trainer.py: contains the training & evaluation code

  constituency/parse_tree.py: a data structure for representing a parse tree and utility methods
  constituency/tree_reader.py: a module which can read trees from a string or input file

  constituency/tree_stack.py: a linked list which can branch in
    different directions, which will be useful when implementing beam
    search or a dynamic oracle

  constituency/parse_transitions.py: transitions and a State data structure to store them
  constituency/transition_sequence.py: turns ParseTree objects into
    the transition sequences needed to make them

  constituency/base_model.py: operates on the transitions to turn them in to constituents,
    eventually forming one final parse tree composed of all of the constituents
  constituency/lstm_model.py: adds LSTM features to the constituents to predict what the
    correct transition to make is, allowing for predictions on previously unseen text

  stanza/pipeline/constituency_processor.py: interface between this model and the Pipeline
"""

import argparse
import logging
import os

import torch

from stanza.models.common import utils
from stanza.models.constituency import trainer
from stanza.models.constituency.parse_transitions import TransitionScheme

logger = logging.getLogger('stanza')

def parse_args(args=None):
    parser = argparse.ArgumentParser()

    parser.add_argument('--data_dir', type=str, default='data/constituency', help='Directory of constituency data.')

    parser.add_argument('--wordvec_dir', type=str, default='extern_data/wordvec', help='Directory of word vectors')
    parser.add_argument('--wordvec_file', type=str, default='', help='File that contains word vectors')
    parser.add_argument('--wordvec_pretrain_file', type=str, default=None, help='Exact name of the pretrain file to read')
    parser.add_argument('--pretrain_max_vocab', type=int, default=250000)

    parser.add_argument('--tag_embedding_dim', type=int, default=20, help="Embedding size for a tag")
    parser.add_argument('--delta_embedding_dim', type=int, default=100, help="Embedding size for a delta embedding")

    parser.add_argument('--train_file', type=str, default=None, help='Input file for data loader.')
    parser.add_argument('--eval_file', type=str, default=None, help='Input file for data loader.')
    parser.add_argument('--mode', default='train', choices=['train', 'predict', 'remove_optimizer'])

    parser.add_argument('--lang', type=str, help='Language')
    parser.add_argument('--shorthand', type=str, help="Treebank shorthand")

    parser.add_argument('--transition_embedding_dim', type=int, default=20, help="Embedding size for a transition")
    parser.add_argument('--transition_hidden_size', type=int, default=20, help="Embedding size for transition stack")
    parser.add_argument('--hidden_size', type=int, default=100, help="Size of the output layers for constituency stack and word queue")

    parser.add_argument('--epochs', type=int, default=200)
    parser.add_argument('--eval_interval', type=int, default=5000)
    # 30 is slightly slower than 50, for example, but seems to train a bit better on WSJ
    # earlier version of the model (less accurate overall) had the following results with adadelta:
    #  30: 0.9085
    #  50: 0.9070
    #  75: 0.9010
    # 150: 0.8985
    # as another data point, running a newer version with better constituency lstm behavior had:
    #  30: 0.9111
    #  50: 0.9094
    # checking smaller batch sizes to see how this works, at 135 epochs, the values are
    #  10: 0.8919
    #  20: 0.9072
    #  30: 0.9121
    # obviously these experiments aren't the complete story, but it
    # looks like 30 trees per batch is the best value for WSJ
    # eval batch should generally be faster the bigger the batch,
    # up to a point, as it allows for more batching of the LSTM
    # operations and the prediction step
    parser.add_argument('--train_batch_size', type=int, default=30, help='How many trees to train before taking an optimizer step')
    parser.add_argument('--eval_batch_size', type=int, default=50, help='How many trees to batch when running eval')

    parser.add_argument('--save_dir', type=str, default='saved_models/constituency', help='Root dir for saving models.')
    parser.add_argument('--save_name', type=str, default=None, help="File name to save the model")
    parser.add_argument('--save_latest_name', type=str, default=None, help="Save the latest model here regardless of score.  Useful for restarting training")

    parser.add_argument('--seed', type=int, default=1234)
    parser.add_argument('--cuda', type=bool, default=torch.cuda.is_available())
    parser.add_argument('--cpu', action='store_true', help='Ignore CUDA.')

    DEFAULT_LEARNING_RATES = { "adamw": 0.001, "adadelta": 1.0, "sgd": 0.001 }
    parser.add_argument('--learning_rate', default=None, type=float, help='Learning rate for the optimizer.  Reasonable values are 1.0 for adadelta or 0.001 for SGD.  None uses a default for the given optimizer: {}'.format(DEFAULT_LEARNING_RATES))
    # When using adadelta, weight_decay of 0.01 to 0.001 had the best results.
    # 0.1 was very clearly too high. 0.0001 might have been okay.
    parser.add_argument('--weight_decay', default=0.01, type=float, help='Weight decay (eg, l2 reg) to use in the optimizer')
    parser.add_argument('--optim', default='Adadelta', help='Optimizer type: SGD, AdamW, or Adadelta')

    # When using dropout in conjunction with relu, one particular experiment produced the following dev scores after 300 iterations:
    # 0.0: 0.9085
    # 0.2: 0.9165
    # 0.4: 0.9162
    # 0.5: 0.9123
    # Letting 0.2 and 0.4 run for longer, along with 0.3 as another
    # trial, continued to give extremely similar results over time.
    # No attempt has been made to test the different dropouts separately...
    parser.add_argument('--word_dropout', default=0.2, type=float, help='Dropout on the word embedding')
    parser.add_argument('--predict_dropout', default=0.2, type=float, help='Dropout on the final prediction layer')

    parser.add_argument('--transition_scheme', default=TransitionScheme.TOP_DOWN, type=lambda x: TransitionScheme[x.upper()],
                        help='Transition scheme to use.  {}'.format(", ".join(x.name for x in TransitionScheme)))

    parser.add_argument('--constituency_lstm', default=False, action='store_true', help="Build constituents using the full LSTM instead of just the nodes below the new constituent.  Doesn't match the original papers and might be slightly less effective")

    # relu gave at least 1 F1 improvement over tanh in various experiments
    # relu & gelu seem roughly the same, but relu is clearly faster.
    # relu, 496 iterations: 0.9176
    # gelu, 467 iterations: 0.9181
    # after the same clock time on the same hardware.  the two had been
    # trading places in terms of accuracy over those ~500 iterations.
    parser.add_argument('--nonlinearity', default='relu', choices=['tanh', 'relu', 'gelu'], help='Nonlinearity to use in the model.  relu is a noticeable improvement')

    parser.add_argument('--rare_word_unknown_frequency', default=0.02, type=float, help='How often to replace a rare word with UNK when training')
    parser.add_argument('--rare_word_threshold', default=0.02, type=float, help='How many words to consider as rare words as a fraction of the dataset')

    parser.add_argument('--num_lstm_layers', default=2, type=int, help='How many layers to use in the LSTMs')
    parser.add_argument('--num_output_layers', default=2, type=int, help='How many layers to use at the prediction level')

    # TODO: add the ability to keep training in a different direction
    # after making an error, eg, add an oracle
    parser.add_argument('--train_method', default='gold_entire', choices=['gold_entire'], help='Different training methods to use')

    parser.add_argument('--finetune', action='store_true', help='Load existing model during `train` mode from `load_name` path')
    parser.add_argument('--maybe_finetune', action='store_true', help='Load existing model during `train` mode from `load_name` path if it exists.  Useful for running in situations where a job is frequently being preempted')
    parser.add_argument('--load_name', type=str, default=None, help='Model to load when finetuning, evaluating, or manipulating an existing file')

    args = parser.parse_args(args=args)
    if not args.lang and args.shorthand and len(args.shorthand.split("_")) == 2:
        args.lang = args.shorthand.split("_")[0]
    if args.cpu:
        args.cuda = False
    if args.learning_rate is None:
        args.learning_rate = DEFAULT_LEARNING_RATES.get(args.optim.lower(), None)

    args = vars(args)
    return args

def main(args=None):
    args = parse_args(args=args)

    utils.set_random_seed(args['seed'], args['cuda'])

    logger.info("Running constituency parser in {} mode".format(args['mode']))
    logger.debug("Using GPU: {}".format(args['cuda']))

    model_save_file = args['save_name'] if args['save_name'] else '{}_constituency.pt'.format(args['shorthand'])
    model_save_file = os.path.join(args['save_dir'], model_save_file)

    model_save_latest_file = None
    if args['save_latest_name']:
        model_save_latest_file = os.path.join(args['save_dir'], args['save_latest_name'])

    model_load_file = model_save_file
    if args['load_name']:
        model_load_file = os.path.join(args['save_dir'], args['load_name'])
    elif args['mode'] == 'train' and args['save_latest_name']:
        model_load_file = model_save_latest_file

    if args['mode'] == 'train':
        trainer.train(args, model_save_file, model_load_file, model_save_latest_file)
    elif args['mode'] == 'predict':
        trainer.evaluate(args, model_load_file)
    elif args['mode'] == 'remove_optimizer':
        trainer.remove_optimizer(args, model_save_file, model_load_file)

if __name__ == '__main__':
    main()
