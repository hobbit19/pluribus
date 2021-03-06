import argparse
import numpy as np
import logging
from leduc.cfr.regret_min import RegretMin
from leduc.cfr.vanilla_cfr import VanillaCFR
from leduc.cfr.mccfr import MonteCarloCFR
from leduc.game.card import Card
from leduc.game.state import State, LeducState
from leduc.game.hand_eval import kuhn_eval, leduc_eval


parser = argparse.ArgumentParser(description='Counterfactual Regret Minimization')
parser.add_argument('-i', '--iterations', type=int, help='number of iterations to run for.')
parser.add_argument('-c','--cfr', type=int, help='(0) Run regret min or Run CFR for (1): 2 players or (2): 3 players')
parser.add_argument('-b', '--raises', default=1, type=int, help='Number of raises per round')
parser.add_argument('-a', '--actions', default=2, type=int, help='Number of actions')
parser.add_argument('-g', '--game', type=int, default=0, help='Game to run (0) Kuhn or (1) Leduc')
parser.add_argument('-m', '--mccfr', type=int, help='(1) Run MCCFR for two player kuhn poker or (2) 3 players')
args = parser.parse_args()

if args.cfr == 0: 
    print("Running regret minimization for RPS with strat [.4, .3, .3]")
    utilities = np.array([[[0, -1, 1], [1, 0, -1], [-1, 1, 0]], [[0, 1, -1], [-1, 0, 1], [1, -1, 0]]])
    minimization = RegretMin(3, utilities[0], np.array([.4, .3, .3]))
    minimization.train(args.iterations)
    print(minimization.avg_strategy())

elif args.cfr == 1:
    settings = {'num_players':2}

    if args.game == 1:
        cards = [Card(12, 1), Card(13, 1), Card(14, 1), Card(12, 2), Card(13, 2), Card(14, 2)]
        settings['num_actions'] = 3
        settings['hand_eval'] = leduc_eval
        settings['num_rounds'] = 2
        settings['num_raises'] = 2
        settings['raise_size'] = [2,4]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'leduc'
        settings['state'] = LeducState
    else:
        cards = [Card(12, 1), Card(13, 1), Card(14, 1)]
        settings['hand_eval'] = kuhn_eval
        settings['num_rounds'] = 1
        settings['num_raises'] = 1
        settings['num_actions'] = args.actions
        settings['raise_size'] = [1]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'kuhn'
        settings['state'] = State
        

    kuhn_regret = VanillaCFR(settings)
    kuhn_regret.train(cards, args.iterations)
    
elif args.cfr == 2:
    settings = {'num_players':3}

    if args.game == 1:
        cards = [Card(11, 1), Card(12, 1), Card(13, 1), Card(14, 1), Card(11, 2), Card(12, 2), Card(13, 2), Card(14, 2)]
        settings['num_actions'] = 3
        settings['hand_eval'] = leduc_eval
        settings['num_rounds'] = 2
        settings['num_raises'] = 2
        settings['raise_size'] = [2,4]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'leduc'
        settings['state'] = LeducState
    else:
        cards = [Card(11, 1), Card(12, 1), Card(13, 1), Card(14, 1)]
        settings['hand_eval'] = kuhn_eval
        settings['num_rounds'] = 1
        settings['num_raises'] = 1
        settings['num_actions'] = args.actions
        settings['raise_size'] = [1]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'kuhn'
        settings['state'] = State

    three_kuhn = VanillaCFR(settings)
    three_kuhn.train(cards, args.iterations)

elif args.mccfr == 1:
    settings = {'num_players':2}

    if args.game == 1:
        cards = [Card(12, 1), Card(13, 1), Card(14, 1), Card(12, 2), Card(13, 2), Card(14, 2)]
        settings['num_actions'] = 3
        settings['hand_eval'] = leduc_eval
        settings['num_rounds'] = 2
        settings['num_raises'] = 2
        settings['raise_size'] = [2,4]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'leduc'
        settings['state'] = LeducState
    else:
        cards = [Card(12, 1), Card(13, 1), Card(14, 1)]
        settings['hand_eval'] = kuhn_eval
        settings['num_rounds'] = 1
        settings['num_raises'] = 1
        settings['num_actions'] = args.actions
        settings['raise_size'] = [1]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'kuhn'
        settings['state'] = State

    mccfr = MonteCarloCFR(settings)
    mccfr.train(cards, args.iterations)

elif args.mccfr == 2:
    cards = np.array([i for i in range(1, 5)])
    settings = {'num_players':3}
                
    if args.game == 1:
        cards = [Card(11, 1), Card(12, 1), Card(13, 1), Card(14, 1), Card(11, 2), Card(12, 2), Card(13, 2), Card(14, 2)]
        settings['num_actions'] = 3
        settings['hand_eval'] = leduc_eval
        settings['num_rounds'] = 2
        settings['num_raises'] = 2
        settings['raise_size'] = [2,4]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'leduc'
        settings['state'] = LeducState
    else:
        cards = [Card(11, 1), Card(12, 1), Card(13, 1), Card(14, 1)]
        settings['hand_eval'] = kuhn_eval
        settings['num_rounds'] = 1
        settings['num_raises'] = 1
        settings['num_actions'] = args.actions
        settings['raise_size'] = [1]
        settings['num_cards'] = settings['num_players'] + settings['num_rounds'] - 1
        settings['game'] = 'kuhn'
        settings['state'] = State
        
    mccfr = MonteCarloCFR(settings)
    mccfr.train(cards, args.iterations)
    
else:
    parser.print_help()