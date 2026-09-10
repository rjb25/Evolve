import cProfile
import pstats
from tools import tools
from survivor import Survivor
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

message = 4 #input("control id?")
tools.set_control_id(int(message))
runs = 8000

with cProfile.Profile() as profile:
    #PEASANTS
    for i in range(count):
        peasant = Survivor()
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
        for peasant in tools.get_members("peasants"):
            if peasant.health > 0:
                peasant.live()
                peasant.act()

        #Remove dead
        reduced = []
        for peasant in tools.get_members("peasants"):
            if peasant.alive():
                reduced.append(peasant)
            else:
                tools.del_member("peasants",peasant)
        peasants = reduced

        #Log
        for peasant in tools.get_members("peasants"):
            print(peasant)

        #Performance
        if tools.performance_run:
            runs -= 1

results = pstats.Stats(profile)
results.sort_stats(pstats.SortKey.TIME)
results.print_stats()
results.dump_stats("results.prof")





