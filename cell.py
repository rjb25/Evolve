from tools import tools
from dna import dna
import random
import dna
class Cell:
    def __init__(self,**kwargs):
        self.mass = 100
        self.energy = 50
        self.duration = 100
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
        tools.add_member("cells",self)


    def __str__(self):
        return str(self.id) + " " + self.name + " " + str(self.energy) + " " + self.action + " " + str(self.activity) +" "+ str(self.last_target) + " " + str(self.reward) + " spent" + str(self.spent)

    def act(self,animal):
        if self.id == tools.get_control_id():
            try:
                actionindex = int(input("cell action?"))
            except (ValueError, TypeError):
                actionindex = 1
            if actionindex-1 < len(self.options):
                action = self.options[actionindex-1]
            else:
                action = self.options[0]
        else:
            action = tools.choice(self.options,self.weights)
        self.action = action
        self.last_target = ""
        out = {}
        match action:
            #Every turn you alot energy into drinking from the soup
            #Contribute Eat Punish allotment for compete/attack.
            #rest can have allotment for grow which increases your max output and max storage. Rest also decreases your decay and aging.
            #Breed you can choose if the child is high or low potential. You can prefer longevity or efficiency. Invest high vs low.

            #The animal will also have a tax rate.
            #Possibly have a rot factor on mass where mass is lost Forcing you to grow at a certain rate or die.
            #If your mass is around 10x that of another cell you can start eating smaller cells.
            case "compete":
                #could make compete a dict itself
                grow = self.compete[0]
                eat = self.compete[1]
                share = self.compete[2]
                activity = self.activity*self.energy
                self.energy -= activity
                self.spent = activity
                self.last_target = self.compete
                return {"cell":self,"grow":grow*activity,"share":share*activity,"eat":eat*activity,"reap":eat*self.activity}

            case "rest":
                if animal.action == "rest":
                    self.energy += 1

            case "breed":
                #Need a mutation chance where new dna name is put in? Maybe add another letter each time a mutant varies. Have mutation chance be a thing. Have budge distance from where it is. Each additional time it gets less?
                if self.energy > 20:
                    self.energy -= 10
                    animal.cells.append(Cell(**{"energy":10,"name":self.name, "activity":self.activity,"compete":self.compete,"weights":self.weights}))




