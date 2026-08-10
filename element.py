from tools import tools
from dna import dna
import random
import dna
import string
class Element:
    def __init__(self,**kwargs):
        self.energy = 50
        self.options = ["compete","rest","breed"]
        self.weights = tools.make_weights(len(self.options))
        self.activity = random.random()
        self.action = "rest"
        self.compete = tools.make_weights(3)
        self.excess = tools.make_weights(2)
        self.last_target = ""
        self.reward = 0
        self.spent = 0
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "name"):
            self.name = dna.make_word(1)
        self.id = tools.unique_id()
        tools.add_cell_dict(self)


    def __str__(self):
        return str(self.id) + " " + self.name + " " + str(self.energy) + " " + self.action + " " + str(self.activity) +" "+ str(self.last_target) + " " + str(self.reward) + " spent" + str(self.spent)

    def act(self, elements):
        #Act till you have singularity
        seek = dna.laws[self.name]
        random_letter = "a"





