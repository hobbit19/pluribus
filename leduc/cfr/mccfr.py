import numpy as np
import random
from itertools import permutations
from tqdm import tqdm
from collections import defaultdict
from leduc.cfr.vanilla_cfr import VanillaCFR
from leduc.cfr.node import InfoSet

class MonteCarloCFR(VanillaCFR):
    """An object to run Monte Carlo Counter Factual Regret 

    Unlike VanillaCFR, Monte Carlo samples the actions of the opponent
    and of chance (called external sampling) by traversing as one player. This way, we don't need to 
    traverse the entire tree like we do in VanillaCFR. We are able to reach similar
    results with MonteCarloCFR in the same number iterations as VanillaCFR, but we touch
    fewer number of nodes than VanillaCFR. In this implementation, we also implement
    pruning for actions that have incredibly negative regret and linear discounting
    for the first part of running so that early actions, which tend to be worse, 
    don't dominate later on in the running of the simulation.


    Attributes:
        num_players: An integer of players playing
        num_actions: An integer of actions
        actions: A list of strings of the allowed actions
        __custom_payoff: a method to determine different payoffs (only used for multiplayer)
        terminal: a list of strings of the terminal states in the game
        node_map: a dictionary of nodes of each information set
        num_betting_rounds: int of number of betting rounds
        num_raises: int of max number of raises per round
        regret_minimum: int for the threshold to prune
        strategy_interval: int when to update the strategy sum
        prune_threshold: int for when to start pruning
        discount_interval: int for at n iterations, when to discount
        lcfr_threshold: int for when to discount
        action_mapping: dict of actions to int
        reverse_mapping: dict of ints to action
    """
    
    def __init__(self, json, **kwargs):
        """initializes the object

        See object attributes for params
        """
        super().__init__(json, **kwargs)
        self.regret_minimum = -300000
        self.strategy_interval = 100
        self.prune_threshold = 200
        self.discount_interval = 100
        self.lcfr_threshold = 400
        self.continuation = set(('1', '2', '3', '4'))

    def train(self, cards, iterations):
        """Runs MonteCarloCFR and prints the calculated strategies
        
        Prints the average utility for each player at the
        end of training and also the optimal strategies

        Args:
            cards: array-like of ints denoting each card
            iterations: int for number of iterations to run
        """
        self.state_json['cards'] = cards
        shuffle = random.shuffle
        for t in tqdm(range(1, iterations+1), desc='Training'):
            shuffle(cards)
            for player in range(self.num_players):
                state = self.state(self.state_json)
                if t % self.strategy_interval == 0:
                    self.update_strategy(player, state)
                if t > self.prune_threshold:
                    will_prune = random.random()
                    if will_prune < .05:
                        self.mccfr(player, state)
                    else:
                        self.mccfr(player, state, prune=True)
                else:
                    self.mccfr(player, state)

            if t < self.lcfr_threshold and t % self.discount_interval == 0:
                self.discount(t)

        expected_utilities = self.expected_utility(cards)
        for player in range(self.num_players):
            print("expected utility for player {}: {}".format(
                player, expected_utilities[player]))
            player_info_sets = self.node_map[player]
            print('information set:\tstrategy:\t')
            for key in sorted(player_info_sets.keys(), key=lambda x: (len(x), x)):
                node = player_info_sets[key]
                strategy = node.avg_strategy()
                if self.json['game'] == 'kuhn':
                    if self.num_actions == 2:
                        print("{}:\t P: {} B: {}".format(key, strategy['P'], strategy['B']))
                    else:
                        print("{}:\t F: {} P: {} C: {} R: {}".format(
                            key, strategy['F'], strategy['P'], strategy['C'], strategy['R']))

                else:
                    print("{}:\t F: {} C: {} R: {}".format(key, strategy['F'], strategy['C'], strategy['R']))

    def discount(self, t):
        discount = (t/self.discount_interval)/((t/self.discount_interval)+ 1)
        for player in range(self.num_players):
            player_nodes = self.node_map[player]
            for node in player_nodes.values():
                node.regret_sum = {key:value * discount for key,value in node.regret_sum.items()}
                node.strategy_sum = {key:value * discount for key,value in node.strategy_sum.items()}

    def mccfr(self, player, state, prune=False):
        """Main function that runs the MonteCarloCFR

        Args:
            cards: array-like of ints denoting each card
            history: str of public betting history
            player: int of which player we are traversing with
            prune: boolean of whether to prune or not

        Returns:
            array_like: float of expected utilities
        """
        if state.is_terminal:
            utility = state.payoff()
            return np.array(utility)

        curr_player = state.turn
        
        if curr_player == player:
            info_set = state.info_set
            player_nodes = self.node_map.setdefault(curr_player, {})
            node = player_nodes.setdefault(info_set, InfoSet(self.actions))

            valid_actions = state.valid_actions
            strategy = node.strategy(valid_actions)

            expected_value = np.zeros(self.num_players)
            utilities = {action:0 for action in valid_actions}
            if prune:
                explored = set()

            for a in valid_actions:
                if prune:
                    if node.regret_sum[a] > self.regret_minimum:
                        new_state = state.add(player, a)
                        calculated_util = self.mccfr(player, new_state, prune=True)
                        utilities[a] = calculated_util[curr_player]
                        expected_value += calculated_util * strategy[a]
                        explored.add(a)
                else:
                    new_state = state.add(player, a)
                    calculated_util = self.mccfr(player, new_state)
                    utilities[a] = calculated_util[curr_player]
                    expected_value += calculated_util * strategy[a]
            
            for a in valid_actions:
                if prune:
                    if a in explored:
                        regret = utilities[a] - expected_value[curr_player]
                        node.regret_sum[a] += regret
                else:
                    regret = utilities[a] - expected_value[curr_player]
                    node.regret_sum[a] += regret

            return expected_value

        else:
            info_set = state.info_set
            player_nodes = self.node_map.setdefault(curr_player, {})
            node = player_nodes.setdefault(info_set, InfoSet(self.actions))

            valid_actions = state.valid_actions
            strategy = node.strategy(valid_actions)
            actions = list(strategy.keys())
            prob = list(strategy.values())
            random_action = random.choices(actions, weights=prob)[0]
            new_state = state.add(curr_player, random_action)
            return self.mccfr(player, new_state, prune=prune)


    def update_strategy(self, player, state):
        """After running for a fixed number of iterations, update the average
        strategies
        
        Since we are running a Monte Carlo process, we can't update
        the strategy sum after iteration. We run for a fixed number of iterations
        (strategy_interval) and then update the strategy so as to be sure that
        the regrets are up to date with the current strategy

        Args:
            history: str of public betting history
            player: int of which player we are updating
        """
        if state.is_terminal:
            return
        
        curr_player = state.turn
        if curr_player == player:
            info_set = state.info_set
            player_nodes = self.node_map.setdefault(curr_player, {})
            node = player_nodes.setdefault(info_set, InfoSet(self.actions))
            
            valid_actions = state.valid_actions
            strategy = node.strategy(valid_actions)

            actions = list(strategy.keys())
            prob = list(strategy.values())
            random_action = random.choices(actions, weights=prob)[0]

            node.strategy_sum[random_action] += 1

            new_state = state.add(player, random_action)
            self.update_strategy(player, new_state)

        else:
            info_set = state.info_set
            player_nodes = self.node_map.setdefault(curr_player, {})
            node = player_nodes.setdefault(info_set, InfoSet(self.actions))

            valid_actions = state.valid_actions
            for a in valid_actions:
                new_state = state.add(curr_player, a)
                self.update_strategy(player, new_state)

    def subgame_solve(self, nature, strategy, iterations):
        self.strategy = defaultdict(lambda: defaultdict(lambda: InfoSet(self.actions)))
        for t in tqdm(range(1, iterations+1), desc='Subgame solving'):
            root = random.choice(nature.children)
            for player in range(self.num_players):
                if t % self.strategy_interval == 0:
                    self.subgame_update_strategy(player, root)
                if t > self.prune_threshold:
                    will_prune = np.random.random()
                    if will_prune < .05:
                        self.subgame_mccfr(player, root)
                    else:
                        self.subgame_mccfr(player, root, prune=True)
                else:
                    self.subgame_mccfr(player, root)

            if t < self.lcfr_threshold and t % self.discount_interval == 0:
                discount = (t/self.discount_interval)/(t/self.discount_interval+ 1)
                for player in range(self.num_players):
                    player_nodes = self.strategy[player]
                    for node in player_nodes.values():
                        node.regret_sum = {key:value * discount for key,value in node.regret_sum.items()}
                        node.strategy_sum = {key:value * discount for key,value in node.strategy_sum.items()}

        return self.strategy

    def subgame_mccfr(self, player, tree_node, prune=False):
        if tree_node.state.is_terminal:
            utility = tree_node.state.payoff()
            return np.array(utility)

        curr_player = tree_node.state.turn

        if curr_player == player:
            info_set = tree_node.state.info_set
            node = self.strategy[curr_player][info_set]

            if not node.is_frozen:
                valid_actions = tree_node.state.valid_actions if not tree_node.is_leaf else self.continuation
                strategy = node.strategy(valid_actions)
                expected_value = np.zeros(self.num_players)
                utilities = {action:0 for action in valid_actions}
                if tree_node.is_leaf:
                    # need to somehow have actions for continuation strategy
                    if prune:
                        explored = set()

                    for a in valid_actions:
                        if prune:
                            if node.regret_sum[a] > self.regret_minimum:
                                calculated_util = tree_node.value(curr_player, self.node_map, a)
                                utilities[a] = calculated_util[curr_player]
                                expected_value += calculated_util * strategy[a]
                                explored.add(a)
                        else:
                            calculated_util = tree_node.value(curr_player, self.node_map, a)
                            utilities[a] = calculated_util[curr_player]
                            expected_value += calculated_util * strategy[a]
                else:
                    if prune:
                        explored = set()

                    for a in valid_actions:
                        if prune:
                            if node.regret_sum[a] > self.regret_minimum:
                                next_tree_node = tree_node.children[a]
                                calculated_util = self.subgame_mccfr(player, next_tree_node, prune=True)
                                utilities[a] = calculated_util[curr_player]
                                expected_value += calculated_util * strategy[a]
                                explored.add(a)
                        else:
                            next_tree_node = tree_node.children[a]
                            calculated_util = self.subgame_mccfr(player, next_tree_node)
                            utilities[a] = calculated_util[curr_player]
                            expected_value += calculated_util * strategy[a]
                
                for a in valid_actions:
                    if prune:
                        if a in explored:
                            regret = utilities[a] - expected_value[curr_player]
                            node.regret_sum[a] += regret
                    else:
                        regret = utilities[a] - expected_value[curr_player]
                        node.regret_sum[a] += regret

                return expected_value
            else:
                #you've already encountered this info set in the game and made a decision
                raise NotImplementedError('Frozen action for infoset')

        else:
            info_set = tree_node.state.info_set
            node = self.strategy[curr_player][info_set]
            if not node.is_frozen:
                valid_actions = tree_node.state.valid_actions if not tree_node.is_leaf else self.continuation
                strategy = node.strategy(valid_actions)

                actions = list(strategy.keys())
                prob = list(strategy.values())
                random_action = random.choices(actions, weights=prob)[0]
                if tree_node.is_leaf:
                    calculated_util = tree_node.value(curr_player, self.node_map, random_action)
                    return calculated_util
                else:
                    next_tree_node = tree_node.children[random_action]
                    return self.subgame_mccfr(player, next_tree_node, prune=prune)

            else:
                #you've already encountered this info set in the game and made a decision
                raise NotImplementedError('Frozen action for infoset')
   
    def subgame_update_strategy(self, player, tree_node):
        if tree_node.state.is_terminal:
            return

        curr_player = tree_node.state.turn
        if curr_player == player:
            info_set = tree_node.state.info_set
            node = self.strategy[curr_player][info_set]
            if not node.is_frozen:
                if tree_node.is_leaf:
                    valid_actions = self.continuation
                    strategy = node.strategy(valid_actions)

                    actions = list(strategy.keys())
                    prob = list(strategy.values())
                    random_action = random.choices(actions, weights=prob)[0]
                    node.strategy_sum[random_action] += 1
                    return
                else:
                    valid_actions = tree_node.state.valid_actions
                    strategy = node.strategy(valid_actions)

                    actions = list(strategy.keys())
                    prob = list(strategy.values())
                    random_action = random.choices(actions, weights=prob)[0]
                    node.strategy_sum[random_action] += 1
                    next_tree_node = tree_node.children[random_action]
                    self.subgame_update_strategy(player, next_tree_node)
            else:
                # take action 
                raise NotImplementedError("Frozen action for infoset")

        else:
            info_set = tree_node.state.info_set
            node = self.strategy[curr_player][info_set]
            valid_actions = tree_node.state.valid_actions
            if not node.is_frozen:
                if tree_node.is_leaf:
                    strategy = node.strategy(self.continuation)

                    actions = list(strategy.keys())
                    prob = list(strategy.values())
                    random_action = random.choices(actions, weights=prob)[0]
                    node.strategy_sum[random_action] += 1
                    return
                else:
                    for a in valid_actions:
                            next_tree_node = tree_node.children[a]
                            self.subgame_update_strategy(player, next_tree_node)
            else:
                raise NotImplementedError('Frozen action for infoset')

    
    def expected_utility(self, cards):
        """Calculates the expected utility from the average strategy

        Traverses every combination of cards dealt to calculate 
        the expected utility based on the probability of playing
        each action by each player. This only works for 2 player Kuhn
        poker currently

        Args:
            cards: array_like of ints of cards, where each 
                index corresponds to a player

        Returns:
            array_like: floats that correspond to each players expected
                utility
        """
        all_combos = [list(t) for t in set(permutations(cards, self.num_cards))]

        expected_utility = np.zeros(self.num_players)
        for card in tqdm(all_combos):
            self.state_json['cards'] = card
            state = self.state(self.state_json)
            expected_utility += self.traverse_tree(state)

        return expected_utility/len(all_combos)


    def traverse_tree(self, state):
        """Helper funtion that traverses the tree to calculate expected utility

        Calculates the strategy profile from the average strategy 
        and calculates the expected utility based on the probability of
        taking that action

        Args:
            history: str of betting history
            player: int for which player
            card: array_like of ints for that dealing of private cards

        Returns:
            util: array_like of floats for expected utility for this node
        """
        if state.is_terminal:
            utility = state.payoff()
            return np.array(utility)
        try:
            player = state.turn
            info_set = state.info_set
            player_nodes = self.node_map.setdefault(player, {})
            node = player_nodes.setdefault(info_set, InfoSet(self.actions))

            strategy = node.avg_strategy()
            util = np.zeros(self.num_players)
            valid_actions = state.valid_actions
            for a in valid_actions:
                new_state = state.add(player, a)
                util += self.traverse_tree(new_state) * strategy[a]

            return util

        except:
            raise UserWarning("\nUnexplored information set: {}\
                \nYou may need to train for more iterations to reach all possible states".format(info_set))
            