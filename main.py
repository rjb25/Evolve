import dna
import cell
import tools

message = "" # Initialize message to an empty string
creatures = 3
my_creatures = []
enemy_creatures = []

def initiate():
    global my_creatures
    global enemy_creatures
    my_creatures = []
    enemy_creatures = []
    for i in range(creatures):
        my_creature = Cell({"team":"good"})
        my_creatures.append(my_creature)
        enemy_creature = Cell({"team":"evil"})
        enemy_creature["team"] = "evil"
        enemy_creatures.append(enemy_creature)

initiate()
my_current = 0
enemy_current = 0
while message != 'quit':
    good = my_creatures[my_current]
    bad = enemy_creatures[enemy_current]
    print(bad)
    for creature in my_creatures:
        print(creature)
    message = input("Action?") # Get user input inside the loop
    match message:
        case "a":
            good["health"] -= bad["damage"]
            bad["health"] -= good["damage"]

        case "quit":
            wordtest = "aaaaaa"
            to_wordtest = "aaaaaa"
            functiontest = "count"
            damagetest = evaluate(functiontest,wordtest,to_wordtest)
            print("testing")
            print(wordtest)
            print(to_wordtest)
            print(damagetest)
        case _:
            if message.isnumeric() and int(message)<len(my_creatures):
                my_creatures.insert(0,my_creatures.pop(int(message)))
    if good["health"]<=0:
        my_creatures.pop(0)
    if bad["health"]<=0:
        enemy_creatures.pop(0)
    if not(enemy_creatures):
        print("victory!")
        initiate()
    if not(my_creatures):
        print("defeat!")
        initiate()

        #case "close":
        #lev_dist = textdistance.levenshtein.distance(word, to_word)
        #sum += math.floor((len(word)/1.5)/lev_dist)
