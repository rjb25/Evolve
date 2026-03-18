import cProfile
import pstats
from tools import tools
from animal import Animal

message = "" # Initialize message to an empty string
count = 10
animals = []

def initiate():
    global animals
    global count
    animals = []
    for i in range(count):
        animal = Animal(**{"team":"evil"})
        animals.append(animal)

initiate()
message = 4 #input("control id?")
tools.set_control_id(int(message))
tools.my_cell_dict[tools.get_control_id()] = tools.cell_dict[tools.get_control_id()]
tools.my_dna = tools.cell_dict[tools.get_control_id()].name
runs = 80

with cProfile.Profile() as profile:
    while runs:
        animal_exists = tools.animal_dict.get(tools.get_control_id())
        cell_exists = tools.cell_dict.get(tools.get_control_id())
        if not animal_exists and not cell_exists and not tools.performance_run:
            control_id = tools.get_new_id()
            if control_id:
                print("died. You are now: "+str(control_id))
                tools.set_control_id(int(control_id))
            else:
                print("game_over")
                runs = 0

        for animal in animals:
            animal.act(animals)

        reduced_animals = []
        for animal in animals:
            if animal.cells:
                reduced_animals.append(animal)
            else:
                tools.pop_animal_dict(animal)

        animals = reduced_animals
        if tools.animal_dict.get(tools.get_control_id()):
            for animal in animals:
                print(animal)
        if tools.performance_run:
            runs -= 1
results = pstats.Stats(profile)
results.sort_stats(pstats.SortKey.TIME)
results.print_stats()
results.dump_stats("results.prof")





