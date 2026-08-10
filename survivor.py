from tools import tools
from dna import dna
import random
import dna
import string
#I have a good interaction system. But I need a good unifying anc creation system.
#Add a peasant every round
#Allow peasants to insure, which means that they join a group who share damage and share reward. Same for knights.
#You have a social coordinate, target etc, rest (heal,  craft), and an attack action attack, grow.
class Survivor:
    def __init__(self,**kwargs):
        self.health = 20
        self.goods = 10
        self.deck = ["new"]
        self.options = ["rest","eat","explore","attack"]
        self.weights = tools.make_weights(len(self.options))
        self.last_target = ""
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "name"):
            self.name = dna.make_word(6)
        self.id = tools.unique_id()


    def __str__(self):
        #Need a print tool
        return str(self.id) + " " + self.name + " Health:" + str(self.health) + " Goods:" + str(self.goods) + " Do:" + self.action

    def get_defense(self):
        return self.offense

    def get_offense(self):
        return self.offense

    def take(self, amount):
        self.goods = max(0,self.goods-amount)
        return min(self.goods,amount)

    def give(self, receiver, amount):
        goods = self.take(amount)
        if receiver:
            receiver.goods += goods

    def damage(self,attacker):
        self.health -= attacker.offense
        if self.health <= 0:
            self.give(attacker,self.goods)

    def alive(self):
        return self.health > 0

    def act(self, state):
        #Act till you have singularity
        if self.id == tools.get_control_id():
            try:
                actionindex = int(input("Peasant action?"))
                action = self.options[actionindex - 1]
            except (ValueError, TypeError,IndexError):
                actionindex = 1
                action = self.options[actionindex - 1]
        else:
            action = tools.choice(self.options, self.weights)

        self.action = action
        target = self.random_target(state)

        match action:
            case "new":
                if target:
                    self.last_target = target.id
                    if target.tolerate > self.tax:
                        target.give(self,self.tax)

                    else:
                        fights = max(self.fights, target.fights)
                        for fight in range(fights):
                            if target.alive() and self.alive():

                                defense = target.get_defense()
                                offense = self.get_offense()
                                whole = defense + offense
                                #Both parties lose effort put in, and only attacker stands to gain.
                                if random.random() * whole < offense:
                                    target.damage(self)
                                else:
                                    self.damage(target)

            case "job":
                if target:
                    self.last_target = target.id
                    mine = self.cut
                    theirs = self.cut
                    leftover = 1 - mine - theirs
                    reward = 10
                    if leftover >= 0:
                        self.goods += round(mine * reward)
                        target.goods += round(theirs * reward)

    def live(self):
        heal = round(self.goods/10)
        true = self.take(heal)
        self.health += round(true/3) -1

    def random_target(self,state):
        #This has equal distance. For all
        #What about indexing that moves a certain distance.
        # Could have various interaction likelihoods
        # One method would be to store likelihood of interaction and allow both creatures to modify that. Would have to have a likelihood for n^2 items. This is a storage issue, not a performance issue.
        #What does the data structure look like?
        # A dict for every id that has
        # Randomize victor based on cell count
        #Make a mega dict. Headache to update with killings and spawnings. Possibly add your own personal list to theirs? Performance tanks, but the idea is still there.
        #Alternatively you could just use xyz.
        #Maintain a vector by adding up all likelihoods to get a total chance. Do this while also looping for a random selection. Could do a binary search tree if performance is an issue.
        # Have a vector of Items for each peasant containing: A reference, a likelihood(relative, or maybe not?)
        # You then random select a float between 0 and the max value. say you get 37. You go through the vector adding up values till you are past the float and selecting that item. You could also just do random.choice from a dict containing id and likelihood pairs. choice weights are values and choices are keys
        valid = False
        target = 0
        while not (valid):
            if len(state) < 2:
                return False
            else:
                target = random.choice(state)
                if target.id != self.id:
                    return target

            #case "rest": is actually just a passthrough

survivor = Survivor()