import tools
import random
class Cell:
    def __init__(self,**kwargs):
        self.energy = 100
        self.options = ["attack","rest","breed"]
        self.weights = tools.generate_random_integers_summing_to_100(len(self.options))
        self.attack = random.random()
        for key, value in kwargs.items():
            setattr(self,key,value)
