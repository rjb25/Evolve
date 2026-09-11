from __future__ import annotations


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


class Registry:
    def __init__(self, rng):
        self.rng = rng
        self.current_id = 0
        self.group = {}

    def unique_id(self):
        self.current_id += 1
        return self.current_id

    def get_member(self, group, id):
        return get_nested(self.group, [group, id])

    def get_members(self, group):
        members = get_nested(self.group, [group])
        if not members:
            return []
        return list(members.values())

    def del_member(self, group, member):
        del self.group[group][member.id]

    def add_member(self, group, member):
        set_nested(self.group, [group, member.id], member)

    def choice(self, options, probs):
        x = self.rng.random()
        cum = 0
        i = 0
        for prob in probs:
            cum += prob
            if x < cum:
                return options[i]
            i += 1
        return options[-1]

    def make_weights(self, num_count):
        if num_count <= 0:
            return []
        numbers = []
        for i in range(num_count):
            num = self.rng.random()
            numbers.append(num)
        total = sum(numbers)
        return [float(i) / total for i in numbers]
