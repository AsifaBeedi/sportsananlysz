class OpponentModel:
    def __init__(self):
        self.weak_to = []

    def update(self, shot, success):
        if not success:
            self.weak_to.append(shot)

    def get_weakness(self):
        if len(self.weak_to) == 0:
            return "unknown"
        
        return max(set(self.weak_to), key=self.weak_to.count)