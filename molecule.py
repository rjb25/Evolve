from tools import tools
from dna import dna
import random
import dna
import string
class Molecule:
    def __init__(self,elements,**kwargs):
        self.elements = elements
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "name"):
            self.name = dna.make_word(1)
        self.id = tools.unique_id()


    def __str__(self):
        return str(self.id) + " " + self.name + " " + str(self.energy) + " " + self.action + " " + str(self.activity) +" "+ str(self.last_target) + " " + str(self.reward) + " spent" + str(self.spent)

    def act(self, elements):
        #Act till you have singularity
        seek = dna.laws[self.name]
        random_letter = "a"
