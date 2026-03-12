#Notes
#Free functions which have a range of maxima
#Allow words of infinite length Make most of the longer words capable of a lot of power.
#what if you graphed this?
#Good games have a strong variety of threat types. Good games mimick real life well. Ebb and flow of difficulty
#Different scales of systems
#interlocking systems
#Games that can be played by a computer or by a person. That encapsulate into another game.
#Engine incapsulation
#Make a bunch of games that could or could not be visualized
#For example a 3x3 grid of entities that can attack eat share etc. The grid is populated with entities regularly.
#In fact each cell has multiple entities. These entities can interact at various ranges with surrounding cells. They also have spandrils.
#These spandrils create the stats of larger entities that can interact with adjacent cells as well.
import random
import string
import textdistance
import math

word_length = 6
rule_count = 10
functions = ["count","approach"]
def make_rule():
    return {"function":random.choice(functions)}
def make_word():
    the_word =""
    for i in range(word_length):
        random_letter = random.choice(string.ascii_lowercase)
        the_word += random_letter
    return the_word
word = make_word()
print(word)


def calculate(word, rules):
    useful = []
    sum = 0
    best_sum = 0
    best_rule ={}
    for rule in rules:
        if not rule.get("to_word"):
            rule["to_word"] = make_word()
        ruleout = evaluate(rule["function"], word, rule["to_word"])
        rule["output"] = ruleout
        if ruleout:
            useful.append(rule)
        sum += ruleout
        if sum > best_sum:
            best_sum = sum
            best_rule = rule

    print(word)
    print(best_rule)
    return sum

def letter_distance(char1,char2):
    char1 = char1.lower()
    char2 = char2.lower()
    # Use ord() to get the integer value (ASCII/Unicode) of each character
    distance = abs(ord(char1) - ord(char2))
    return distance


def evaluate(rule, word, to_word):
    sum = 0
    match rule:
        case "count":
            i = 1
            for letter in to_word:
                sum += word.count(to_word[0:i]) * i * i/2
                i += 1

        case "approach":
            for i in range(min(len(word),len(to_word))):
                distance = letter_distance(word[i],to_word[i])
                sum += (25-distance)/25
            sum -= 3
            sum = max(0,sum)
            sum = sum*sum

    return sum


rules = []
for i in range(rule_count):
    rules.append(make_rule())
health_rules = []
damage_rules = []
for i in range(rule_count):
    health_rules.append(make_rule())
    damage_rules.append(make_rule())


def generate_random_integers_summing_to_100(num_count):
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

def make_creature(word):
    creature = {}
    creature["health"] = 0.1+ calculate(word,health_rules)
    creature["energy"] = 100
    creature["options"] = ["attack","rest","breed"]
    creature["weights"] = generate_random_integers_summing_to_100(len(creature["options"]))
    creature["attack"] = random.random()
    creature["damage"] = 0.1+ calculate(word,damage_rules)
    creature["dna"] = word
    return creature

damage = calculate(word,rules)
print(rules)
print(damage)

class Rule:
    def __init__(self):
        self.name = "shmame"
rulio = Rule()


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
        message = input("Enter DNA")  # Get user input inside the loop
        my_creature = make_creature(message)
        my_creature["team"] = "good"
        my_creatures.append(my_creature)
        enemy_creature = make_creature(make_word())
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
