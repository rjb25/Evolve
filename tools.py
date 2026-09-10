import random
import string
import textdistance
import math
class Tool:
    def __init__(self):
        self.current_id = 1
        self.my_id = 1
        self.performance_run = 0
        #Some point this should be group dict where string is passed in to associate with group
        self.group = {}
        self.my_cell_dict = {}
        self.animal_dict = {}
        self.my_animal_dict = {}
        self.my_dna = ""


    def unique_id(self):
        self.current_id += 1
        return self.current_id

    def get_control_id(self):
        return self.my_id

    def get_new_id(self):
        new_cells = list(self.my_cell_dict.values())
        if new_cells:
            return new_cells[0].id
        else:
            return 0

    def set_control_id(self,my_id):
        self.my_id = my_id

    def get_member(self,group,id):
        return get_nested(self.group,[group,id])

    def get_members(self,group):
        return list(get_nested(self.group,[group]).values())

    def del_member(self,group,member):
        del self.group[group][member.id]
        if member.name == self.my_dna:
            del self.group[group+"_mine"][member.id]

    def add_member(self,group,member):
        set_nested(self.group, [group, member.id],member)
        if member.name == self.my_dna:
            set_nested(self.group, [group+"_mine", member.id],member)

    #def add_relation(self,member,other_member):
    #    append_nested(self.group, ["relations",member.id],member)
    #    append_nested(self.group, ["relations",member.id],member)
    #    if member.name == self.my_dna:
    #        set_nested(self.group, [group+"_mine", member.id],member)

    def del_member(self,group,member):
        del self.group[group][member.id]
        if member.name == self.my_dna:
            del self.group[group+"_mine"][member.id]

    def choice(self, options, probs):
        x = random.random()
        cum = 0
        i = 0
        for prob in probs:
            cum += prob
            if x < cum:
                return options[i]
            i += 1

    def generate_random_integers_summing_to_100(self,num_count):
        """
        Generates a list of 'num_count' random integers (>= 0) that sum to 100.
        """
        if num_count <= 0:
            return []

        numbers = []
        remaining_sum = 100

        for i in range(num_count - 1):
            # The next random number must be between 0 and the remaining sum
            num = random.randint(0, remaining_sum)
            numbers.append(num)
            remaining_sum -= num

        # The last number is exactly the remaining sum
        numbers.append(remaining_sum)
        return numbers

    def make_weights(self,num_count):
        if num_count <= 0:
            return []

        numbers = []

        for i in range(num_count):
            num = random.random()
            numbers.append(num)
        all = sum(numbers)
        norm = [float(i) / all for i in numbers]

        return norm

    def generate_random_integers_summing_to_100(self,num_count):
        """
        Generates a list of 'num_count' random integers (>= 0) that sum to 100.
        """
        if num_count <= 0:
            return []

        numbers = []
        remaining_sum = 100

        for i in range(num_count - 1):
            # The next random number must be between 0 and the remaining sum
            num = random.randint(0, remaining_sum)
            numbers.append(num)
            remaining_sum -= num

        # The last number is exactly the remaining sum
        numbers.append(remaining_sum)
        return numbers

def get_nested(data, keys):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            return None
        data = data[key]

    return data.get(keys[-1])

def set_nested(data, keys, value):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]

    data[keys[-1]] = value

def try_nested(data, keys, value):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            return
        data = data[key]

    data[keys[-1]] = value

def append_nested(data, keys, value):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]

    if data.get(keys[-1]):
        data[keys[-1]].append(value)
    else:
        data[keys[-1]] = [value]

def extend_nested(data, keys, value):
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]

    if data.get(keys[-1]):
        data[keys[-1]].extend(value)
    else:
        data[keys[-1]] = value

tools = Tool()

class Shop:
    def init(self):
        self.inventory = {"options":[{"item":"sword", "damage":2, "cost":5}]}

    def stock(self, item):
        self.inventory["options"].append(item)

