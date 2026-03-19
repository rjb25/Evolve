from tools import tools
import random
import dna
from cell import Cell
class Animal:
    def __init__(self,**kwargs):
        self.start = 10
        self.cells = []
        self.options = ["attack","rest","breed"]
        self.weights = tools.make_weights(len(self.options))
        self.offense = random.random()
        self.defense = random.random()/2
        self.action = "rest"
        self.last_target = ""
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id = tools.unique_id()
        if not hasattr(self, "name"):
            self.name = dna.make_word()
        if not self.cells:
            for i in range(self.start):
                self.cells.append(Cell(**{"animal":self}))
        else:
            for cell in self.cells:
                cell.animal = self
        tools.add_animal_dict(self)

    def __str__(self):
        return str(self.id) + " " + self.name + " " + str(len(self.cells)) + " " + self.action + " " + str(self.last_target)

    def act(self,state):
        if self.id == tools.get_control_id():
            try:
                actionindex = int(input("cell action?"))
            except (ValueError, TypeError):
                actionindex = 1
            action = self.options[actionindex-1]
        else:
            action = tools.choice(self.options, self.weights)
        self.action = action
        self.last_target = ""
        self.live()
        match action:
            case "attack":
                #Randomize victor based on cell count
                valid = False
                target = 0
                while not(valid):
                    if len(state) < 2:
                        valid = True
                    else:
                        target = random.choice(state)
                        if target.id != self.id:
                            valid = True
                if target:
                    self.last_target = target.id

                    defense = target.get_defense()
                    offense = self.get_offense()
                    whole = defense + offense
                    #Both parties lose effort put in, and only attacker stands to gain.
                    if random.random() * whole < offense:
                        #In addition to energy put into defense if you lose an attack you lose the whole effort sum again.
                        if target.cells:
                            random_index = random.randrange(len(target.cells))
                            random_cell = target.cells.pop(random_index)
                            self.cells.append(random_cell)
                            random_cell.animal = self

            #case "rest": is actually just a passthrough

            case "breed":
                if len(self.cells) > 3:
                    random_index = random.randrange(len(self.cells))
                    random_cell = self.cells.pop(random_index)
                    state.append(Animal(**{"cells":[random_cell], "name":self.name, "weights":self.weights,  "defense":self.defense, "offense":self.offense}))

    def live(self):
        name_count = {}

        rewards = {"pot":0,"eats":0,"reaps":0, "share":0}
        players = []
        for cell in self.cells:
            cell.reward = 0
            output = cell.act(self)
            if output:
                players.append(output)
                rewards["pot"] += output["grow"] * 3
                rewards["eats"] += output["eat"]
                rewards["reaps"] += output["reap"]
                rewards["share"] += output["share"] * 1.5
            #Checking for the dominant cell name
            if not name_count.get(cell.name):
                name_count[cell.name] = 1
            else:
                name_count[cell.name] += 1

        self.offense = rewards["eats"]
        rewards["pot"] -= rewards["share"]

        #compete content
        for player in players:
            reward = (player["eat"]/rewards["eats"]) * rewards["pot"]
            reward += (player["reap"]/rewards["reaps"]) * rewards["share"]
            player["cell"].energy += reward
            player["cell"].reward = reward

        #kill content
        reduced_cells = []
        for cell in self.cells:
            cell.energy -= 1
            if cell.energy > 0.0001:
                reduced_cells.append(cell)
            else:
                tools.pop_cell_dict(cell)
        self.cells = reduced_cells

        control_cell = tools.cell_dict.get(tools.get_control_id())
        #If the controlled cells animal id is my id print my cells
        if control_cell and control_cell.animal.id == self.id:
            print("reward " + str(rewards["pot"]) + ", share " + str(rewards["share"]))
            for cell in self.cells:
                print(cell)
        if name_count:
            self.name = max(name_count, key=name_count.get)


    def get_defense(self):
        return self.offense

    def get_offense(self):
        return self.offense



