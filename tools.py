import random
import string
import textdistance
import math
class Tool:
    def __init__(self):
        self.current_id = 1
        self.my_id = 1
        self.performance_run = 0
        self.cell_dict = {}
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

    def add_cell_dict(self,cell):
        self.cell_dict[cell.id] = cell
        if cell.name == self.my_dna:
            self.my_cell_dict[cell.id] = cell

    def pop_cell_dict(self,cell):
        del self.cell_dict[cell.id]
        if cell.name == self.my_dna:
            del self.my_cell_dict[cell.id]

    def add_animal_dict(self,animal):
        self.animal_dict[animal.id] = animal
    def pop_animal_dict(self,animal):
        del self.animal_dict[animal.id]

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

tools = Tool()