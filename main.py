import cProfile
import pstats
from tools import tools
from animal import Animal
from peasant import Peasant
from survivor import Survivor
from element import Element
#What do I want? I want infinite generation of meaning to allow a game to create a need for the player to modify their flow for a very long time.
#I achieve this with many systems of interacting parts.
#Systems are Object interactions, object unifications, object modifications.
#Have more varied objects fuels further system interactions to be more complex.
# Object interactions create new content because of every interaction of different types has different meaning.
# Object unifications increase meaning by way of combinatorics. In a way where items are not simply being summed.
#Object interactions can simply be a list of things to do and a list of resources to spend and targets to effect
#Object unifications are meant to allow more complex "Entities" to form without having to actually make new entities.

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

#initiate()
message = 0 #input("control id?")
tools.set_control_id(int(message))
#our_cell.energy += 50
#tools.my_dna = our_cell.name
runs = 80

with cProfile.Profile() as profile:
    #SURVIVORS
    #survivors = []
    #for i in range(10):
    #    survivor = Survivor()
    #    survivors.append(survivor)
    #    tools.add_member("survivors",survivor)

    #while runs:
    #    print("survive")
    #    #Check which is yours
    #    alive = tools.get_member("survivors",tools.get_control_id())
    #    if not alive and not tools.performance_run:
    #        control_id = tools.get_new_id()
    #        if control_id:
    #            print("died. You are now: "+str(control_id))
    #            tools.set_control_id(int(control_id))
    #            confirm = input("confirm")
    #        else:
    #            message = input("DIED. control id?")
    #            tools.set_control_id(int(message))
    #            #print("game_over")
    #            #runs = 0

    #    #Main action
    #    for survivor in survivors:
    #        if survivor.health > 0:
    #            survivor.act(survivors)
    #            survivor.live()

    #    #Remove dead
    #    reduced = []
    #    for survivor in survivors:
    #        if survivor.health > 0:
    #            reduced.append(survivor)
    #        else:
    #            tools.del_member("survivors",survivor)
    #    survivors = reduced
    #    for survivor in survivors:
    #        print(survivor)

    #PEASANTS
    peasants = []
    for i in range(1):
        peasant = Survivor()
        peasants.append(peasant)
        tools.add_member("peasants",peasant)

    while runs:
        #Check which is yours
        alive = tools.get_member("peasants",tools.get_control_id())
        if not alive and not tools.performance_run:
            control_id = tools.get_new_id()
            if control_id:
                print("died. You are now: "+str(control_id))
                tools.set_control_id(int(control_id))
                confirm = input("confirm")
            else:
                message = input("DIED. control id?")
                tools.set_control_id(int(message))
                #print("game_over")
                #runs = 0

        #Main action
        for peasant in peasants:
            if peasant.health > 0:
                peasant.act(peasants)
                peasant.live()

        #Remove dead
        reduced = []
        for peasant in peasants:
            if peasant.health > 0:
                reduced.append(peasant)
            else:
                tools.del_member("peasants",peasant)
        peasants = reduced
        for peasant in peasants:
            print(peasant)


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





