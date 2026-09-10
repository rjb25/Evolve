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
        self.action = "none"
        self.health = 20
        self.meat = 20
        self.water = 20
        self.fiber = 20
        self.isplayer = 0
        #self.information = 1
        #self.negotiation = 1
        self.trade = ["meat","water","fiber"]#,"information","negotiation"]
        self.produce = random.choice(["meat","water","fiber"])
        self.options = ["produce","deal","relate"]
        self.weights = tools.make_weights(len(self.options))
        self.relations = []
        self.last_target = ""
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "name"):
            self.name = dna.make_word(6)
        self.id = tools.unique_id()


    def __str__(self):
        #Need a print tool
        out_string = str(self.id) + " " + self.name + " Health:" + str(self.health) + " Goods: m" + str(self.meat) + " w" + str(self.water) + " f" + str(self.fiber) + " Do:" + self.action #+" Information:" + str(self.information) + " Negotiation:"+str(self.negotiation)
        if self.isplayer:
            out_string = out_string + " ME"
        return out_string

    def alive(self):
        return self.health > 0

    def act(self):
        #Act till you have singularity
        if self.id == tools.get_control_id():
            self.isplayer = 1
            try:
                actionindex = int(input("Survivor action? (number)"))
                action = self.options[actionindex]
            except (ValueError, TypeError,IndexError):
                actionindex = 0
                action = self.options[actionindex]
        else:
            self.isplayer = 0
            action = tools.choice(self.options, self.weights)

        self.action = action
        target = self.random_target()

        match action:
            case "produce":
                setattr(self, self.produce, getattr(self, self.produce) + 20)

            case "deal":
                #self.negotiation += 2
                if self.relations:
                    dealt = random.choice(self.relations)
                    friend = tools.get_member("peasants",dealt)
                    if self.isplayer:
                        print(self.relations)
                        print(dealt)
                        print(friend)
                    if friend:
                        giving = self.excess()
                        getting = self.need()
                        decision = friend.decide(giving,getting,self)
                        if decision:
                            setattr(self, getting, getattr(self, getting)+10)
                            setattr(friend, giving, getattr(friend, giving)+10)

                            setattr(self, giving, getattr(self, giving)-9)
                            setattr(friend, getting, getattr(friend, getting)-9)
                    else:
                        if tools.get_members("peasants"):
                            if self.isplayer:
                                print(self.relations)
                                print(dealt)
                            self.relations.remove(dealt)

            case "relate":
                #self.information += 2
                if target:
                    if target.id not in self.relations:
                        self.relations.append(target.id)
                        target.relations.append(self.id)

    def decide(self, receive, give, friend):
        giving = getattr(self,give)
        receiving = getattr(self,receive)
        if friend.isplayer:
            print("Friend " + self.name)
            print("Gives, to get")
            print(give, receive)
            print(giving, receiving -1 )
            print(giving > receiving - 1)
        #I have more of what I am giving than what I am receiving
        return giving > receiving -1


    def excess(self):
        best = -1000000
        best_option = ""
        for option in  self.trade:
            stock = getattr(self, option)
            if stock > best:
                best = getattr(self,option)
                best_option = option
        return  best_option

    def need(self):
        best = 10000000
        best_option = ""
        for option in  self.trade:
            stock = getattr(self, option)
            if stock < best:
                best = getattr(self,option)
                best_option = option
        return  best_option

    def live(self):
        goods = min(self.meat,self.water,self.fiber)
        if goods > 0:
            self.meat -= 1
            self.water -= 1
            self.fiber -= 1
            if self.health < 20:
                self.health += 2
        else:
            self.health -= 4
            self.meat -= 1
            self.water -= 1
            self.fiber -= 1



    def random_target(self):
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
        state = tools.get_members("peasants")
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
